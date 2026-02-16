import os
import uvicorn


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8910"))

    uvicorn.run("assertive_mock_api_server.app:app", host="0.0.0.0", port=port)
