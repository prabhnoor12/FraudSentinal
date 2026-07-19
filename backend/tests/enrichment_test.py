from unittest.mock import patch, MagicMock


def test_enrichment_lookup_ip(client):
    # Register and login to get token
    client.post(
        "/auth/register",
        json={
            "email": "geo@test.com",
            "password": "StrongPass123!",
            "organisation_name": "Geo",
        },
    )
    token = client.post(
        "/auth/login", json={"email": "geo@test.com", "password": "StrongPass123!"}
    ).json()["access_token"]

    mock_geo = MagicMock()
    mock_geo.country_code = "US"
    mock_geo.region = "California"
    mock_geo.city = "Mountain View"
    mock_geo.latitude = 37.386
    mock_geo.longitude = -122.0838
    mock_geo.isp = "Google"

    with patch(
        "cruds.ip_geolocation_crud.get_geolocation_by_ip", return_value=mock_geo
    ):
        response = client.get(
            "/enrichment/ip-geolocation/lookup?ip_address=8.8.8.8",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["country_code"] == "US"
        assert data["city"] == "Mountain View"


def test_enrichment_lookup_bin(client):
    # Register and login to get token
    client.post(
        "/auth/register",
        json={
            "email": "bin@test.com",
            "password": "StrongPass123!",
            "organisation_name": "Bin",
        },
    )
    token = client.post(
        "/auth/login", json={"email": "bin@test.com", "password": "StrongPass123!"}
    ).json()["access_token"]

    mock_bin = MagicMock()
    mock_bin.bin_number = "424242"
    mock_bin.card_brand = "Visa"
    mock_bin.card_type = "Credit"
    mock_bin.issuing_bank = "Chase"
    mock_bin.issuing_country_code = "US"
    mock_bin.is_prepaid = False
    mock_bin.risk_score = 10

    with patch("cruds.bin_lookup_crud.get_bin_by_number", return_value=mock_bin):
        response = client.get(
            "/enrichment/bin-lookup/lookup?bin_number=424242",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["card_brand"] == "Visa"
        assert data["issuing_bank"] == "Chase"


def test_enrichment_signals_integration(client):
    # This tests the /signals/test endpoint which combines both
    client.post(
        "/auth/register",
        json={
            "email": "sig@test.com",
            "password": "StrongPass123!",
            "organisation_name": "Sig",
        },
    )
    token = client.post(
        "/auth/login", json={"email": "sig@test.com", "password": "StrongPass123!"}
    ).json()["access_token"]

    mock_geo = MagicMock()
    mock_geo.country_code = "US"
    mock_geo.available = True

    mock_bin = MagicMock()
    mock_bin.card_brand = "Visa"
    mock_bin.available = True

    # We need to mock the services used in enrichment_service
    with (
        patch("services.enrichment_service._enrich_ip_geolocation") as mock_ip,
        patch("services.enrichment_service._enrich_bin_data") as mock_card,
    ):
        from services.enrichment_service import IPGeoSignals, BINSignals

        mock_ip.return_value = IPGeoSignals(
            geolocation_available=True, ip_country_code="US"
        )
        mock_card.return_value = BINSignals(
            bin_available=True,
            card_brand="Visa",
            card_type="Credit",
            issuing_country_code="US",
            is_prepaid=False,
            bin_risk_score=10,
        )

        response = client.get(
            "/enrichment/signals/test?ip_address=8.8.8.8&card_number=4242424242424242&billing_country=US",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["signals"]["ip_country"] == "US"
        assert data["signals"]["card_brand"] == "Visa"
        assert data["signals"]["ip_billing_country_mismatch"] is False
