from fastapi import status


def test_register_user(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "test@example.com",
            "password": "StrongPass123!",
            "organisation_name": "Test Org",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data


def test_login_user(client):
    # First register
    client.post(
        "/auth/register",
        json={
            "email": "login@example.com",
            "password": "StrongPass123!",
            "organisation_name": "Login Org",
        },
    )

    # Then login
    response = client.post(
        "/auth/login", json={"email": "login@example.com", "password": "StrongPass123!"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_get_me(client):
    # Register and login to get token
    client.post(
        "/auth/register",
        json={
            "email": "me@example.com",
            "password": "StrongPass123!",
            "organisation_name": "Me Org",
        },
    )
    login_response = client.post(
        "/auth/login", json={"email": "me@example.com", "password": "StrongPass123!"}
    )
    token = login_response.json()["access_token"]

    # Get me
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["email"] == "me@example.com"


def test_login_invalid_password(client):
    client.post(
        "/auth/register",
        json={
            "email": "wrong@example.com",
            "password": "StrongPass123!",
            "organisation_name": "Wrong Org",
        },
    )

    response = client.post(
        "/auth/login", json={"email": "wrong@example.com", "password": "wrongpassword"}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
