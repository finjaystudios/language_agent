from app.infrastructure.security.passwords import hash_password, verify_password


def test_hash_and_verify_password_with_argon2id():
    password_hash = hash_password("correct horse battery staple", scheme="argon2id")

    assert password_hash != "correct horse battery staple"
    assert verify_password(
        "correct horse battery staple",
        password_hash,
        scheme="argon2id",
    )


def test_wrong_password_fails():
    password_hash = hash_password("super-secret", scheme="argon2id")

    assert not verify_password("not-the-secret", password_hash, scheme="argon2id")


def test_hash_and_verify_password_with_bcrypt():
    password_hash = hash_password("fallback-secret", scheme="bcrypt")

    assert password_hash != "fallback-secret"
    assert verify_password("fallback-secret", password_hash, scheme="bcrypt")
