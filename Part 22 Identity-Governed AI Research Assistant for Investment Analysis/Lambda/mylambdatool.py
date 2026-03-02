import json
import base64
import urllib.request

def lambda_handler(event, context):
    try:
        # OAuth access token passed from AgentCore
        access_token = event.get("access_token")
        file_name = event.get("file_name")

        if not access_token:
            return {"error": "Missing access token"}

        # Step 1: Search for the file in Drive
        search_url = (
            f"https://www.googleapis.com/drive/v3/files"
            f"?q=name+contains+'{file_name}'+and+mimeType='application/pdf'"
            f"&fields=files(id,name)"
        )
        req = urllib.request.Request(search_url)
        req.add_header("Authorization", f"Bearer {access_token}")
        with urllib.request.urlopen(req) as response:
            search_response = json.loads(response.read().decode())
        
        files = search_response.get("files", [])
        if not files:
            return {"error": "File not found"}

        file_id = files[0]["id"]

        # Step 2: Download the PDF
        download_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        req_download = urllib.request.Request(download_url)
        req_download.add_header("Authorization", f"Bearer {access_token}")
        with urllib.request.urlopen(req_download) as file_response:
            pdf_content = file_response.read()

        encoded_pdf = base64.b64encode(pdf_content).decode("utf-8")

        return {
            "file_name": files[0]["name"],
            "file_base64": encoded_pdf
        }

    except Exception as e:
        return {"error": str(e)}