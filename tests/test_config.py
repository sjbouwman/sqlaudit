import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlaudit.config import (
    SQLAuditConfig,
    audit_config,
    clear_config,
    get_config,
    has_config,
    set_config,
)
from sqlaudit.exceptions import SQLAuditConfigError
from tests.utils.db import create_user_model
from sqlaudit._internals.registry import audit_model_registry


@pytest.fixture(scope="function")
def db_session():
    """
    Fixture that provides a fresh in-memory database and DeclarativeBase for each test.
    Returns a tuple of (SessionLocal, Base).
    """
    class Base(DeclarativeBase): ...

    url = "sqlite:///:memory:"
    engine = create_engine(url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    yield SessionLocal, Base
    audit_model_registry.clear()
   
   
def get_db(db_session):
    """Helper function to get a database session."""
    SessionLocal, _ = db_session
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_config_without_user(db_session):
    """
    Test the SQLAuditConfig initialization and validation without user model.
    """
    SessionLocal, _ = db_session
    config = SQLAuditConfig(
        session_factory=lambda: get_db(db_session),
    )

    set_config(config)
    config_retrieved = get_config()

    # Verify that the config is set correctly
    assert config_retrieved.session_factory is not None
    assert config_retrieved.user_model is None
    assert config_retrieved.user_model_user_id_field is None
    assert config_retrieved.get_user_id_callback is None



def test_faulty_config_without_user():
    """
    Test faulty configurations to ensure proper error handling without user model.
    """
    # Test with incorrect session_factory
    with pytest.raises(SQLAuditConfigError):
        SQLAuditConfig(
            session_factory=lambda: "not_a_session",  # type: ignore
        )

    # Test with missing session_factory
    with pytest.raises(TypeError):
        SQLAuditConfig()  # type: ignore

    # Test with non-callable session_factory
    with pytest.raises(SQLAuditConfigError):
        SQLAuditConfig(session_factory="not_callable")  # type: ignore


def test_config_with_user(db_session):
    """
    Test the SQLAuditConfig initialization and validation.
    """
    SessionLocal, Base = db_session

    User = create_user_model(Base)

    # Create a user instance
    user = User()

    # Test the SQLAuditConfig initialization
    config = SQLAuditConfig(
        session_factory=lambda: get_db(db_session),
        user_model=User,
        user_model_user_id_field="user_id",
        get_user_id_callback=lambda: user.user_id
    )

    set_config(config)
    config_retrieved = get_config()

    # Verify that the config is set correctly
    assert config_retrieved.session_factory is not None
    assert config_retrieved.user_model is User
    assert config_retrieved.user_model_user_id_field == "user_id"
    assert config_retrieved.get_user_id_callback is not None
    assert callable(config_retrieved.get_user_id_callback)


def test_faulty_config_with_user_without_callback(db_session):
    """
    Test the SQLAuditConfig initialization and validation with user model but without get_user_id_callback.
    which should raise an error as get_user_id_callback is required when user_model is set.
    """
    SessionLocal, Base = db_session

    User = create_user_model(Base)

    # Test the SQLAuditConfig initialization
    with pytest.raises(SQLAuditConfigError):
        SQLAuditConfig(
            session_factory=lambda: get_db(db_session),
            user_model=User,
            user_model_user_id_field="user_id",
        )


def test_faulty_config_with_user_incorrect_field(db_session):
    """
    Test the SQLAuditConfig initialization and validation with user model but with incorrect user_id field.
    which should raise an error as the user_model_user_id_field does not exist in the User model..
    """
    SessionLocal, Base = db_session


    User = create_user_model(Base)
    # Create a user instance

    user = User()

    # Test the SQLAuditConfig initialization
    with pytest.raises(SQLAuditConfigError):
        SQLAuditConfig(
            session_factory=lambda: get_db(db_session),
            user_model=User,
            user_model_user_id_field="incorrect_field",  # This field does not exist
            get_user_id_callback=lambda: user.user_id,  # type: ignore
        )
def test_faulty_config_with_uncallable_session_factory():
    """
    Test the SQLAuditConfig initialization and validation with an uncallable session_factory.
    which should raise an error as session_factory must return a callable.
    """

    # Test the SQLAuditConfig initialization
    with pytest.raises(SQLAuditConfigError):
        SQLAuditConfig(
            session_factory="not_a_callable", # type: ignore
        )

def test_faulty_config_with_non_string_user_id_field(db_session):
    """
    Test the SQLAuditConfig initialization and validation with a non-string user_model_user_id_field.
    which should raise an error as user_model_user_id_field must be a string.
    """
    SessionLocal, Base = db_session


    User = create_user_model(Base)

    # Test the SQLAuditConfig initialization
    with pytest.raises(SQLAuditConfigError):
        SQLAuditConfig(
            session_factory=lambda: get_db(db_session),
            user_model=User,
            user_model_user_id_field=123,  # type: ignore
            get_user_id_callback=lambda: 1,
        )

def test_faulty_config_with_non_declarative_user_model(db_session):
    """
    Test the SQLAuditConfig initialization and validation with a non-declarative user model.
    which should raise an error as user_model must be a DeclarativeBase subclass.
    """
    SessionLocal, _ = db_session

    # Create a non-declarative user model
    class NonDeclarativeUser:
        pass

    # Test the SQLAuditConfig initialization
    with pytest.raises(SQLAuditConfigError):
        SQLAuditConfig(
            session_factory=lambda: get_db(db_session), # type: ignore
            user_model=NonDeclarativeUser,  # This is not a DeclarativeBase subclass
        )

        
def test_clear_config(db_session):
    """
    Test clearing the SQLAudit configuration.
    """
    SessionLocal, Base = db_session


    User = create_user_model(Base)

    # Create a user instance
    user = User()

    # Set a valid configuration
    config = SQLAuditConfig(
        session_factory=lambda: get_db(db_session),
        user_model=User,
        user_model_user_id_field="user_id",
        get_user_id_callback=lambda: user.user_id,
    )
    set_config(config)

    # Verify configuration is set
    assert has_config() is True

    # Clear the configuration
    clear_config()

    # Verify configuration is cleared
    assert has_config() is False


def test_has_config(db_session):
    """
    Test the has_config function to check if configuration is set.
    """

    _, Base = db_session

    # Initially, no configuration should be set
    assert has_config() is False


    User = create_user_model(Base)

    # Create a user instance
    user = User()

    # Set a valid configuration
    config = SQLAuditConfig(
        session_factory=lambda: get_db(db_session),
        user_model=User,
        user_model_user_id_field="user_id",
        get_user_id_callback=lambda: user.user_id,
    )
    set_config(config)

    # Verify configuration is set
    assert has_config() is True


def test_get_config_without_setting():
    """
    Test get_config raises an error when no configuration is set.
    """
    clear_config()  # Ensure no configuration is set
    with pytest.raises(SQLAuditConfigError):
        get_config()


def test_set_config_with_invalid_type():
    """
    Test set_config raises an error when an invalid type is passed.
    """
    with pytest.raises(SQLAuditConfigError):
        set_config(config="invalid_config")  # type: ignore

def test_get_config_repr(db_session):
    """
    Test the __repr__ method of SQLAuditConfig.
    """
    SessionLocal, Base = db_session

    User = create_user_model(Base)
    # Create a user instance
    user = User()

    # Set a valid configuration
    config = SQLAuditConfig(
        session_factory=lambda: get_db(db_session),
        user_model=User,
        user_model_user_id_field="user_id",
        get_user_id_callback=lambda: user.user_id,
    )

    set_config(config)

    # We check if printing _audit_config gives the expected output
    config_repr = repr(audit_config)
    assert config_repr.startswith("SQLAuditConfigManager"), (
        f"The __repr__ method of SQLAuditConfigManager should start with 'SQLAuditConfigManager'. Got: {config_repr}"
    )
