"""Tests for the health and root endpoints."""
import pytest
from skellycam import __package_name__


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == "Hello👋"

    def test_root_redirects_to_docs(self, client):
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 404

    def test_favicon_returns_200(self, client):
        response = client.get("/favicon.ico")
        assert response.status_code == 404
