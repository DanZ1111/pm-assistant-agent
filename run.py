import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    # Reload only in local development. Disabled on Railway or when DISABLE_RELOAD=1.
    in_production = (
        os.environ.get("RAILWAY_ENVIRONMENT") is not None
        or os.environ.get("DISABLE_RELOAD") == "1"
    )
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=not in_production,
    )
