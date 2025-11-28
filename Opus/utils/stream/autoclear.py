import os
from config import autoclean

async def auto_clean(popped):
    try:
        if isinstance(popped, dict):
            rem = popped.get("file")
        elif isinstance(popped, str):
            rem = popped
        else:
            rem = getattr(popped, "file", None)
        if not rem:
            return
        try:
            while rem in autoclean:
                autoclean.remove(rem)
        except Exception:
            pass
        if rem not in autoclean:
            if not any(p in rem for p in ("vid_", "live_", "index_")):
                try:
                    if os.path.exists(rem):
                        os.remove(rem)
                except Exception:
                    pass
    except Exception:
        pass
