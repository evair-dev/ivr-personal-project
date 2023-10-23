

class TestDocs:

    def test_docs_render(self, test_client):
        response = test_client.get("/api/v1/docs/")
        assert response.status_code == 200
        assert b"IVR API" in response.data