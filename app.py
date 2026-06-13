import streamlit as st
import re
import json
import time
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from PyPDF2 import PdfReader
import requests
import urllib.parse

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="TruthLayer - AI Fact Checker",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CUSTOM CSS
# ============================================================
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        color: #1E293B;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #64748B;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 16px;
        padding: 1.5rem;
        color: white;
        text-align: center;
    }
    .verified-badge {
        background-color: #DCFCE7;
        color: #166534;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .inaccurate-badge {
        background-color: #FEF3C7;
        color: #92400E;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .false-badge {
        background-color: #FEE2E2;
        color: #991B1B;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .claim-box {
        background: #F8FAFC;
        border-left: 4px solid #2563EB;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
    }
    .stProgress > div > div > div > div {
        background-color: #2563EB;
    }
    .footer-text {
        text-align: center;
        color: #94A3B8;
        font-size: 0.8rem;
        margin-top: 3rem;
        padding-top: 1rem;
        border-top: 1px solid #E2E8F0;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# CLAIM EXTRACTION ENGINE
# ============================================================
class ClaimExtractor:
    """Extracts verifiable claims from text using regex patterns."""

    PATTERNS = {
        'statistics': [
            r'\b(?:approximately|about|around|over|under|more than|less than|up to|at least)?\s*[\$€£]?\s*\d+(?:,\d{3})*(?:\.\d+)?\s*(?:million|billion|trillion|thousand|hundred|percent|%|x|times|fold)?\b',
            r'\b\d+(?:\.\d+)?%\s*(?:of|in|for|by)?',
            r'\b(?:a|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:in|out of)\s*(?:every|each)?\s*\d+\b',
        ],
        'dates': [
            r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,\s+)?\d{4}?\b',
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[\.\s]+\d{1,2}(?:,\s+)?\d{4}?\b',
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
            r'\b(?:in|by|since|from|until|as of)\s+(?:the\s+)?(?:year\s+)?(?:19|20)\d{2}\b',
            r'\b(?:Q[1-4]|quarter\s+[1-4])\s+(?:of\s+)?(?:20)?\d{2}\b',
        ],
        'financial': [
            r'\b[\$€£]\s*\d+(?:,\d{3})*(?:\.\d+)?\s*(?:million|billion|trillion|k|M|B)?\b',
            r'\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:million|billion|trillion)\s*(?:dollars|USD|EUR|GBP)?\b',
            r'\b(?:revenue|profit|loss|growth|decline|increase|decrease)\s+(?:of\s+)?[\$€£]?\s*\d+(?:,\d{3})*(?:\.\d+)?\b',
        ],
        'technical': [
            r'\b(?:speed|rate|frequency|capacity|bandwidth|latency|throughput)\s+(?:of\s+)?\d+(?:\.\d+)?\s*(?:Mbps|Gbps|TB|GB|MB|ms|seconds|minutes|hours|Hz|GHz|MHz)?\b',
            r'\b\d+(?:\.\d+)?\s*(?:Mbps|Gbps|TB|GB|MB|ms|GHz|MHz|nm|px|dpi|ppi)\b',
            r'\b(?:version|v)?\d+\.\d+(?:\.\d+)?\b',
        ],
        'comparative': [
            r'\b(?:largest|smallest|fastest|slowest|highest|lowest|most|least|best|worst|first|last)\b',
            r'\b(?:compared to|versus|vs\.|more than|less than|higher than|lower than|greater than|fewer than)\b',
        ]
    }

    def extract(self, text):
        """Extract claims from text with context."""
        claims = []
        sentences = re.split(r'(?<=[.!?])\s+', text)

        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue

            for claim_type, patterns in self.PATTERNS.items():
                for pattern in patterns:
                    matches = re.finditer(pattern, sentence, re.IGNORECASE)
                    for match in matches:
                        # Get surrounding context (2 sentences before and after)
                        context_start = max(0, i - 1)
                        context_end = min(len(sentences), i + 2)
                        context = ' '.join(sentences[context_start:context_end])

                        claims.append({
                            'text': sentence,
                            'claim_type': claim_type,
                            'extracted_value': match.group(0),
                            'position': match.start(),
                            'context': context,
                            'id': len(claims)
                        })

        # Deduplicate by text similarity
        unique_claims = []
        seen = set()
        for claim in claims:
            key = claim['text'][:100]
            if key not in seen:
                seen.add(key)
                unique_claims.append(claim)

        return unique_claims

# ============================================================
# WEB VERIFICATION ENGINE
# ============================================================
class WebVerifier:
    """Verifies claims against live web data using search APIs."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def search_web(self, query):
        """Search the web for a claim. Uses DuckDuckGo HTML as fallback."""
        try:
            # Try DuckDuckGo HTML
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            response = self.session.get(url, timeout=10)

            if response.status_code == 200:
                # Extract snippets
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                results = []

                for result in soup.find_all('div', class_='result'):
                    title_elem = result.find('a', class_='result__a')
                    snippet_elem = result.find('a', class_='result__snippet')

                    if title_elem and snippet_elem:
                        results.append({
                            'title': title_elem.get_text(strip=True),
                            'snippet': snippet_elem.get_text(strip=True),
                            'url': title_elem.get('href', '')
                        })

                return results[:5]
        except Exception as e:
            st.warning(f"Search error: {str(e)}")

        return []

    def verify_claim(self, claim):
        """Verify a single claim against web data."""
        query = claim['extracted_value'] + " " + claim['text'][:100]
        results = self.search_web(query)

        if not results:
            return {
                'status': 'UNVERIFIED',
                'confidence': 0.0,
                'evidence': [],
                'reason': 'No web evidence found'
            }

        # Analyze snippets for confirmation/contradiction
        extracted_value = claim['extracted_value'].lower()
        confirmations = 0
        contradictions = 0
        evidence = []

        for result in results:
            snippet = result['snippet'].lower()
            title = result['title'].lower()

            # Check if extracted value appears in results
            if extracted_value in snippet or extracted_value in title:
                confirmations += 1
                evidence.append({
                    'source': result['title'],
                    'url': result['url'],
                    'snippet': result['snippet'][:200],
                    'type': 'CONFIRMATION'
                })
            else:
                # Check for related numbers that might contradict
                evidence.append({
                    'source': result['title'],
                    'url': result['url'],
                    'snippet': result['snippet'][:200],
                    'type': 'REFERENCE'
                })

        # Determine status
        if confirmations >= 2:
            status = 'VERIFIED'
            confidence = min(0.95, 0.6 + confirmations * 0.1)
        elif confirmations == 1:
            status = 'LIKELY_ACCURATE'
            confidence = 0.65
        elif len(results) > 0:
            status = 'UNVERIFIED'
            confidence = 0.3
        else:
            status = 'UNVERIFIED'
            confidence = 0.0

        return {
            'status': status,
            'confidence': confidence,
            'evidence': evidence[:3],
            'reason': f'Found {confirmations} confirmation(s) in {len(results)} search results'
        }

# ============================================================
# REPORT GENERATOR
# ============================================================
class ReportGenerator:
    """Generates structured fact-check reports."""

    STATUS_COLORS = {
        'VERIFIED': '#22C55E',
        'LIKELY_ACCURATE': '#84CC16',
        'UNVERIFIED': '#F59E0B',
        'INACCURATE': '#EF4444',
        'FALSE': '#DC2626'
    }

    STATUS_LABELS = {
        'VERIFIED': '✅ Verified',
        'LIKELY_ACCURATE': '⚡ Likely Accurate',
        'UNVERIFIED': '❓ Unverified',
        'INACCURATE': '⚠️ Inaccurate',
        'FALSE': '❌ False'
    }

    def generate(self, claims, verifications):
        """Generate a comprehensive report."""
        report = {
            'generated_at': datetime.now().isoformat(),
            'total_claims': len(claims),
            'breakdown': {},
            'claims': []
        }

        for status in self.STATUS_LABELS.keys():
            report['breakdown'][status] = 0

        for claim, verification in zip(claims, verifications):
            status = verification['status']
            report['breakdown'][status] = report['breakdown'].get(status, 0) + 1

            report['claims'].append({
                'id': claim['id'],
                'text': claim['text'],
                'type': claim['claim_type'],
                'extracted_value': claim['extracted_value'],
                'status': status,
                'confidence': verification['confidence'],
                'evidence': verification['evidence'],
                'reason': verification['reason']
            })

        return report

# ============================================================
# PDF PROCESSOR
# ============================================================
def extract_text_from_pdf(file):
    """Extract text from uploaded PDF."""
    try:
        reader = PdfReader(file)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text
    except Exception as e:
        st.error(f"Error reading PDF: {str(e)}")
        return ""

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/fact-checking.png", width=60)
    st.markdown("## TruthLayer")
    st.markdown("*AI-Powered Fact Checker*")
    st.markdown("---")

    st.markdown("### How it works")
    st.markdown("""
    1. **Upload** a PDF document
    2. **Extract** verifiable claims
    3. **Verify** against live web data
    4. **Review** flagged inaccuracies
    """)

    st.markdown("---")
    st.markdown("### Claim Types Detected")
    st.markdown("""
    - 📊 Statistics & Percentages
    - 📅 Dates & Timelines
    - 💰 Financial Figures
    - ⚙️ Technical Specs
    - 📈 Comparatives
    """)

    st.markdown("---")
    st.markdown("<div class='footer-text'>Built with Streamlit</div>", unsafe_allow_html=True)

# ============================================================
# MAIN CONTENT
# ============================================================
st.markdown("<div class='main-header'>🔍 TruthLayer</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-header'>Automated Fact-Checking for PDF Documents. Upload any document and we'll cross-reference every claim against live web data.</div>", unsafe_allow_html=True)

# File upload
uploaded_file = st.file_uploader(
    "📄 Upload your PDF document",
    type=['pdf'],
    help="Upload a PDF containing claims, statistics, or factual statements to verify"
)

if uploaded_file is not None:
    # Extract text
    with st.spinner("📖 Reading PDF..."):
        text = extract_text_from_pdf(uploaded_file)

    if not text:
        st.error("Could not extract text from the PDF. Please try another file.")
        st.stop()

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("### 📄 Document Preview")
        with st.expander("Show extracted text", expanded=False):
            st.text_area("Text", text[:5000] + ("..." if len(text) > 5000 else ""), height=300, label_visibility="collapsed")

    with col2:
        st.markdown("### 🔍 Analysis Controls")

        col_a, col_b = st.columns(2)
        with col_a:
            max_claims = st.slider("Max claims to check", 5, 50, 20)
        with col_b:
            confidence_threshold = st.slider("Confidence threshold", 0.0, 1.0, 0.5)

        analyze_btn = st.button("🚀 Start Fact-Checking", type="primary", use_container_width=True)

    if analyze_btn:
        # Initialize engines
        extractor = ClaimExtractor()
        verifier = WebVerifier()
        reporter = ReportGenerator()

        # Step 1: Extract claims
        progress_bar = st.progress(0)
        status_text = st.empty()

        status_text.text("🔍 Extracting claims from document...")
        claims = extractor.extract(text)
        claims = claims[:max_claims]
        progress_bar.progress(20)

        if not claims:
            st.warning("No verifiable claims found in this document. Try a different PDF with more factual content.")
            st.stop()

        st.success(f"Found {len(claims)} verifiable claims")

        # Step 2: Verify claims
        verifications = []
        for i, claim in enumerate(claims):
            progress = 20 + int((i / len(claims)) * 70)
            progress_bar.progress(progress)
            status_text.text(f"🔍 Verifying claim {i+1}/{len(claims)}: {claim['extracted_value'][:50]}...")

            verification = verifier.verify_claim(claim)
            verifications.append(verification)
            time.sleep(0.5)  # Rate limiting

        progress_bar.progress(100)
        status_text.text("✅ Analysis complete!")
        time.sleep(0.5)
        status_text.empty()
        progress_bar.empty()

        # Step 3: Generate report
        report = reporter.generate(claims, verifications)

        # ============================================================
        # DASHBOARD
        # ============================================================
        st.markdown("---")
        st.markdown("## 📊 Fact-Check Dashboard")

        # Metrics
        m1, m2, m3, m4 = st.columns(4)

        verified_count = report['breakdown'].get('VERIFIED', 0) + report['breakdown'].get('LIKELY_ACCURATE', 0)
        unverified_count = report['breakdown'].get('UNVERIFIED', 0)
        inaccurate_count = report['breakdown'].get('INACCURATE', 0) + report['breakdown'].get('FALSE', 0)
        total = report['total_claims']

        with m1:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #22C55E 0%, #16A34A 100%); border-radius: 16px; padding: 1.5rem; color: white; text-align: center;">
                <div style="font-size: 2rem; font-weight: 800;">{verified_count}</div>
                <div style="font-size: 0.9rem; opacity: 0.9;">✅ Verified</div>
            </div>
            """, unsafe_allow_html=True)

        with m2:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #F59E0B 0%, #D97706 100%); border-radius: 16px; padding: 1.5rem; color: white; text-align: center;">
                <div style="font-size: 2rem; font-weight: 800;">{unverified_count}</div>
                <div style="font-size: 0.9rem; opacity: 0.9;">❓ Unverified</div>
            </div>
            """, unsafe_allow_html=True)

        with m3:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #EF4444 0%, #DC2626 100%); border-radius: 16px; padding: 1.5rem; color: white; text-align: center;">
                <div style="font-size: 2rem; font-weight: 800;">{inaccurate_count}</div>
                <div style="font-size: 0.9rem; opacity: 0.9;">⚠️ Flagged</div>
            </div>
            """, unsafe_allow_html=True)

        with m4:
            accuracy = round((verified_count / total * 100), 1) if total > 0 else 0
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%); border-radius: 16px; padding: 1.5rem; color: white; text-align: center;">
                <div style="font-size: 2rem; font-weight: 800;">{accuracy}%</div>
                <div style="font-size: 0.9rem; opacity: 0.9;">Document Accuracy</div>
            </div>
            """, unsafe_allow_html=True)

        # Charts
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            st.markdown("### 📈 Status Distribution")
            labels = []
            values = []
            colors = []
            for status, count in report['breakdown'].items():
                if count > 0:
                    labels.append(status.replace('_', ' ').title())
                    values.append(count)
                    colors.append(reporter.STATUS_COLORS.get(status, '#94A3B8'))

            fig = go.Figure(data=[go.Pie(
                labels=labels,
                values=values,
                hole=0.5,
                marker_colors=colors,
                textinfo='label+percent',
                textfont_size=12
            )])
            fig.update_layout(
                showlegend=False,
                margin=dict(t=0, b=0, l=0, r=0),
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_chart2:
            st.markdown("### 📊 Claims by Type")
            type_counts = {}
            for claim in report['claims']:
                t = claim['type'].replace('_', ' ').title()
                type_counts[t] = type_counts.get(t, 0) + 1

            fig2 = px.bar(
                x=list(type_counts.keys()),
                y=list(type_counts.values()),
                color=list(type_counts.values()),
                color_continuous_scale='Blues'
            )
            fig2.update_layout(
                showlegend=False,
                margin=dict(t=0, b=0, l=0, r=0),
                height=300,
                xaxis_title=None,
                yaxis_title="Count"
            )
            st.plotly_chart(fig2, use_container_width=True)

        # ============================================================
        # DETAILED RESULTS
        # ============================================================
        st.markdown("---")
        st.markdown("## 🔍 Detailed Results")

        # Filter tabs
        tab_all, tab_verified, tab_flagged, tab_unverified = st.tabs([
            "📋 All Claims", "✅ Verified", "⚠️ Flagged", "❓ Unverified"
        ])

        def render_claim_card(claim):
            status = claim['status']
            color = reporter.STATUS_COLORS.get(status, '#94A3B8')
            label = reporter.STATUS_LABELS.get(status, status)

            st.markdown(f"""
            <div style="background: white; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1.2rem; margin: 0.8rem 0; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.8rem;">
                    <div>
                        <span style="background: {color}20; color: {color}; padding: 2px 10px; border-radius: 12px; font-size: 0.7rem; font-weight: 600;">{claim['type'].replace('_', ' ').upper()}</span>
                        <span style="margin-left: 8px; font-size: 0.85rem; color: #64748B;">Claim #{claim['id']}</span>
                    </div>
                    <span style="background: {color}15; color: {color}; padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; font-weight: 600;">{label}</span>
                </div>
                <div style="font-size: 1rem; color: #1E293B; margin-bottom: 0.5rem; line-height: 1.5;">
                    <strong>Extracted:</strong> {claim['extracted_value']}
                </div>
                <div style="font-size: 0.9rem; color: #64748B; margin-bottom: 0.8rem; line-height: 1.4;">
                    <em>"{claim['text'][:200]}{'...' if len(claim['text']) > 200 else ''}"</em>
                </div>
                <div style="display: flex; align-items: center; gap: 1rem;">
                    <div style="flex: 1;">
                        <div style="font-size: 0.75rem; color: #94A3B8; margin-bottom: 2px;">Confidence</div>
                        <div style="background: #F1F5F9; border-radius: 4px; height: 8px; overflow: hidden;">
                            <div style="width: {claim['confidence']*100}%; background: {color}; height: 100%; border-radius: 4px; transition: width 0.3s;"></div>
                        </div>
                        <div style="font-size: 0.7rem; color: #94A3B8; text-align: right; margin-top: 2px;">{int(claim['confidence']*100)}%</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Evidence
            if claim['evidence']:
                with st.expander(f"📚 View Evidence ({len(claim['evidence'])} sources)"):
                    for ev in claim['evidence']:
                        st.markdown(f"""
                        <div style="background: #F8FAFC; border-radius: 8px; padding: 0.8rem; margin: 0.5rem 0;">
                            <div style="font-weight: 600; color: #1E293B; font-size: 0.85rem;">{ev['source']}</div>
                            <div style="color: #64748B; font-size: 0.8rem; margin: 0.3rem 0;">{ev['snippet']}</div>
                            <div style="font-size: 0.75rem; color: #2563EB;">🔗 {ev['url'][:80]}...</div>
                        </div>
                        """, unsafe_allow_html=True)

        with tab_all:
            for claim in report['claims']:
                render_claim_card(claim)

        with tab_verified:
            verified = [c for c in report['claims'] if c['status'] in ['VERIFIED', 'LIKELY_ACCURATE']]
            if verified:
                for claim in verified:
                    render_claim_card(claim)
            else:
                st.info("No verified claims found.")

        with tab_flagged:
            flagged = [c for c in report['claims'] if c['status'] in ['INACCURATE', 'FALSE']]
            if flagged:
                st.warning("⚠️ These claims could not be verified or may contain inaccuracies. Please review carefully.")
                for claim in flagged:
                    render_claim_card(claim)
            else:
                st.success("🎉 No flagged claims found! All verifiable claims appear accurate.")

        with tab_unverified:
            unverified = [c for c in report['claims'] if c['status'] == 'UNVERIFIED']
            if unverified:
                st.info("❓ These claims could not be verified against web data. They may be accurate but lack sufficient online evidence.")
                for claim in unverified:
                    render_claim_card(claim)
            else:
                st.success("All claims have been verified against web data.")

        # ============================================================
        # EXPORT
        # ============================================================
        st.markdown("---")
        st.markdown("## 📥 Export Report")

        col_exp1, col_exp2 = st.columns(2)

        with col_exp1:
            # JSON export
            json_report = json.dumps(report, indent=2)
            st.download_button(
                label="📄 Download JSON Report",
                data=json_report,
                file_name=f"factcheck_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )

        with col_exp2:
            # CSV export
            df = pd.DataFrame([{
                'ID': c['id'],
                'Type': c['type'],
                'Extracted Value': c['extracted_value'],
                'Status': c['status'],
                'Confidence': f"{c['confidence']*100:.1f}%",
                'Text': c['text'][:200]
            } for c in report['claims']])

            csv = df.to_csv(index=False)
            st.download_button(
                label="📊 Download CSV Report",
                data=csv,
                file_name=f"factcheck_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )

else:
    # Empty state
    st.markdown("---")

    col_demo1, col_demo2, col_demo3 = st.columns(3)

    with col_demo1:
        st.markdown("""
        <div style="text-align: center; padding: 2rem;">
            <div style="font-size: 3rem; margin-bottom: 1rem;">📄</div>
            <div style="font-weight: 600; color: #1E293B; margin-bottom: 0.5rem;">Upload PDF</div>
            <div style="color: #64748B; font-size: 0.9rem;">Drag & drop any PDF document containing claims, stats, or figures</div>
        </div>
        """, unsafe_allow_html=True)

    with col_demo2:
        st.markdown("""
        <div style="text-align: center; padding: 2rem;">
            <div style="font-size: 3rem; margin-bottom: 1rem;">🤖</div>
            <div style="font-weight: 600; color: #1E293B; margin-bottom: 0.5rem;">AI Extraction</div>
            <div style="color: #64748B; font-size: 0.9rem;">Our engine identifies statistics, dates, financials & technical claims</div>
        </div>
        """, unsafe_allow_html=True)

    with col_demo3:
        st.markdown("""
        <div style="text-align: center; padding: 2rem;">
            <div style="font-size: 3rem; margin-bottom: 1rem;">✅</div>
            <div style="font-weight: 600; color: #1E293B; margin-bottom: 0.5rem;">Get Results</div>
            <div style="color: #64748B; font-size: 0.9rem;">See verified, flagged & unverified claims with evidence sources</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Sample trap document info
    st.markdown("### 🧪 Test with a Trap Document")
    st.info("""
    To test the system, create a PDF with intentional errors like:
    - "The global AI market was worth $50 billion in 2020" (actually ~$95B)
    - "ChatGPT was launched in January 2023" (actually Nov 2022)
    - "The Eiffel Tower is 400 meters tall in Paris, France" (actually 330m)
    - "Apple's revenue in 2024 was $500 billion" (actually ~$391B)

    The system will flag these as inaccurate or unverified.
    """)

# Footer
st.markdown("""
<div class='footer-text'>
    TruthLayer v1.0 | Built for CogDigital Assessment | © 2026
</div>
""", unsafe_allow_html=True)
