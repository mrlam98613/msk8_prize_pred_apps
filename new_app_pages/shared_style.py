import streamlit as st


def apply_new_page_style() -> None:
    """Apply shared visual style for new Streamlit 1.64 pages."""
    st.html(
        """
        <style>
        :root {
            --msk-text: #16181d;
            --msk-muted: #5b6472;
            --msk-border: #d7dde7;
            --msk-panel: #f8fafc;
            --msk-accent: #155eef;
        }
        .msk-page-title {
            margin: 0 0 0.35rem;
            color: var(--msk-text);
            font-size: 1.65rem;
            font-weight: 850;
            line-height: 1.25;
        }
        .msk-page-caption {
            margin: 0 0 1rem;
            color: var(--msk-muted);
            font-size: 0.95rem;
            line-height: 1.55;
        }
        .msk-section {
            margin: 0.85rem 0;
            padding: 0.85rem 0;
            border-top: 1px solid var(--msk-border);
        }
        .msk-section-title {
            color: var(--msk-text);
            font-size: 1.05rem;
            font-weight: 800;
            margin-bottom: 0.45rem;
        }
        .msk-note {
            color: var(--msk-muted);
            font-size: 0.9rem;
            line-height: 1.5;
        }
        div[data-testid="stMetric"] {
            background: var(--msk-panel);
            border: 1px solid var(--msk-border);
            border-radius: 8px;
            padding: 0.75rem;
        }
        div[data-testid="stTextInput"] div[data-baseweb="input"] {
            border: 2px solid #667085 !important;
            border-radius: 8px !important;
            background: #ffffff !important;
            box-shadow: inset 0 0 0 1px #667085 !important;
        }
        div[data-testid="stTextInput"] div[data-baseweb="input"]:hover {
            border-color: #475467 !important;
            box-shadow: inset 0 0 0 1px #475467 !important;
        }
        div[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within {
            border-color: var(--msk-accent) !important;
            box-shadow: 0 0 0 2px rgba(21, 94, 239, 0.2), inset 0 0 0 1px var(--msk-accent) !important;
        }
        div[data-testid="stTextInput"] input {
            color: var(--msk-text) !important;
            font-weight: 650 !important;
        }
        </style>
        """
    )


def page_header(title: str, caption: str) -> None:
    """Render a consistent page header."""
    st.html(f'<div class="msk-page-title">{title}</div>')
    st.html(f'<div class="msk-page-caption">{caption}</div>')


def section_title(title: str) -> None:
    """Render a consistent section title."""
    st.html(f'<div class="msk-section-title">{title}</div>')
