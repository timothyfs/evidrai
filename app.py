from __future__ import annotations

# Streamlit Cloud entrypoint. Keep this file intentionally small, but touch it
# when deploy-critical fixes land in imported modules so Cloud visibly rebuilds.
# Rebuild marker: speech-video-audit-mvp.
from evidrai.ui.render import main


if __name__ == "__main__":
    main()
