from sqlalchemy.orm import Mapped, mapped_column


def create_user_model(Base):
    """Helper function to create the User model."""

    class User(Base):
        __tablename__ = "users"
        user_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
        # Add more columns as needed
        first_name: Mapped[str] = mapped_column()
        last_name: Mapped[str] = mapped_column()
        email: Mapped[str] = mapped_column()

        

    return User

