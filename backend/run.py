"""OpsBrief — entry point to run the FastAPI app."""

import uvicorn
from opsbrief.main import app

if __name__ == "__main__":
    uvicorn.run("opsbrief.main:app", host="0.0.0.0", port=8000, reload=True)
