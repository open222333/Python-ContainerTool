from app import create_app
from conf.config import TestingConfig


app = create_app(TestingConfig)


if __name__ == "__main__":
    app.run(debug=True)
