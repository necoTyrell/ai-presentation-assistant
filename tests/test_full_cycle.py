import requests
import time

BASE_URL = "http://localhost:8000"


def test_full_cycle():
    print("🚀 Starting full cycle test...")

    # 1. Check health
    print("1. Checking health...")
    health = requests.get(f"{BASE_URL}/health").json()
    print(f"   Health: {health['status']}")

    # 2. Test LLM
    print("2. Testing LLM...")
    llm_test = requests.post(f"{BASE_URL}/generate/test-llm", json={
        "slide_type": "problem",
        "context": "Тестовый проект AI ассистента",
        "audience": "инвесторы"
    }).json()
    print(f"   LLM test: {llm_test['generation_result']['status']}")

    # 3. Upload test document
    print("3. Uploading test document...")
    with open("test_project.txt", "rb") as f:
        upload_response = requests.post(
            f"{BASE_URL}/upload",
            files={"file": ("test_project.txt", f, "text/plain")}
        ).json()
    print(f"   Upload: {upload_response['status']}")

    # 4. Start presentation generation
    print("4. Starting presentation generation...")
    gen_response = requests.post(f"{BASE_URL}/generate/presentation", json={
        "audience": "инвесторы",
        "presentation_type": "minimal"
    }).json()
    job_id = gen_response["job_id"]
    print(f"   Job started: {job_id}")

    # 5. Wait for completion
    print("5. Waiting for generation...")
    for i in range(30):  # Max 30 attempts
        status = requests.get(f"{BASE_URL}/generate/status/{job_id}").json()
        progress = status["progress"]
        print(f"   Progress: {progress}%")

        if status["status"] == "completed":
            print("   ✅ Generation completed!")
            break
        elif status["status"] == "failed":
            print(f"   ❌ Generation failed: {status['error_message']}")
            return

        time.sleep(5)

    # 6. Download presentation
    if status["status"] == "completed":
        print("6. Downloading presentation...")
        download = requests.get(f"{BASE_URL}/generate/download/{job_id}")
        with open("test_presentation.pptx", "wb") as f:
            f.write(download.content)
        print("   ✅ Presentation saved as test_presentation.pptx")

    print("🎉 Full cycle test completed!")


if __name__ == "__main__":
    test_full_cycle()