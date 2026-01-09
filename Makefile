install:
	poetry install

project:
	poetry run project

lint:
	poetry run ruff check .

build:
	poetry build

package-install:
	python3 -m pip install dist/*.whl

publish:
	poetry publish --dry-run