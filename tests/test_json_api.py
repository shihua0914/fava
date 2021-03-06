# pylint: disable=missing-docstring
import hashlib
from io import BytesIO
from pathlib import Path
from typing import Any
from typing import Optional

import flask
import pytest

from fava.core.misc import align


def assert_api_error(response, msg: Optional[str] = None) -> None:
    """Asserts that the reponse errored and contains the message."""
    assert response.status_code == 200
    assert not response.json["success"]
    if msg:
        assert msg in response.json["error"]


def assert_api_success(response, data: Optional[Any] = None) -> None:
    """Asserts that the request was successful and contains the data."""
    assert response.status_code == 200
    assert response.json["success"]
    if data:
        assert data == response.json["data"]


def test_api_changed(app, test_client) -> None:
    with app.test_request_context():
        app.preprocess_request()
        url = flask.url_for("json_api.changed")

    response = test_client.get(url)
    assert_api_success(response, False)


def test_api_add_document(app, test_client, tmp_path) -> None:
    with app.test_request_context():
        app.preprocess_request()
        old_documents = flask.g.ledger.options["documents"]
        flask.g.ledger.options["documents"] = [str(tmp_path)]
        request_data = {
            "folder": str(tmp_path),
            "account": "Expenses:Food:Restaurant",
            "file": (BytesIO(b"asdfasdf"), "2015-12-12 test"),
        }
        url = flask.url_for("json_api.add_document")

        response = test_client.put(url)
        assert response.status_code == 400

        filename = (
            tmp_path / "Expenses" / "Food" / "Restaurant" / "2015-12-12 test"
        )

        response = test_client.put(url, data=request_data)
        assert_api_success(response, "Uploaded to {}".format(filename))
        assert Path(filename).is_file()

        request_data["file"] = (BytesIO(b"asdfasdf"), "2015-12-12 test")
        response = test_client.put(url, data=request_data)
        assert_api_error(response, "{} already exists.".format(filename))
        flask.g.ledger.options["documents"] = old_documents


def test_api_move(app, test_client) -> None:
    with app.test_request_context():
        app.preprocess_request()
        url = flask.url_for("json_api.move")

        response = test_client.get(url)
        assert_api_error(response)


def test_api_source_put(app, test_client) -> None:
    with app.test_request_context():
        app.preprocess_request()
        url = flask.url_for("json_api.source")

    # test bad request
    response = test_client.put(url)
    assert_api_error(response, "Invalid JSON request.")

    path = app.config["BEANCOUNT_FILES"][0]
    payload = open(path, encoding="utf-8").read()
    sha256sum = hashlib.sha256(open(path, mode="rb").read()).hexdigest()

    # change source
    response = test_client.put(
        url,
        data=flask.json.dumps(
            {
                "source": "asdf" + payload,
                "sha256sum": sha256sum,
                "file_path": path,
            }
        ),
        content_type="application/json",
    )
    sha256sum = hashlib.sha256(open(path, mode="rb").read()).hexdigest()
    assert_api_success(response, sha256sum)

    # check if the file has been written
    assert open(path, encoding="utf-8").read() == "asdf" + payload

    # write original source file
    result = test_client.put(
        url,
        data=flask.json.dumps(
            {"source": payload, "sha256sum": sha256sum, "file_path": path}
        ),
        content_type="application/json",
    )
    assert result.status_code == 200
    assert open(path, encoding="utf-8").read() == payload


def test_api_format_source(app, test_client) -> None:
    with app.test_request_context():
        app.preprocess_request()
        url = flask.url_for("json_api.format_source")

    path = app.config["BEANCOUNT_FILES"][0]
    payload = open(path, encoding="utf-8").read()

    response = test_client.put(
        url,
        data=flask.json.dumps({"source": payload}),
        content_type="application/json",
    )
    assert_api_success(response, align(payload, 61))


def test_api_format_source_options(app, test_client) -> None:
    path = app.config["BEANCOUNT_FILES"][0]
    payload = open(path, encoding="utf-8").read()
    with app.test_request_context():
        app.preprocess_request()
        url = flask.url_for("json_api.format_source")
        old_currency_column = flask.g.ledger.fava_options["currency-column"]
        flask.g.ledger.fava_options["currency-column"] = 90

        response = test_client.put(
            url,
            data=flask.json.dumps({"source": payload}),
            content_type="application/json",
        )
        assert_api_success(response, align(payload, 90))

        flask.g.ledger.fava_options["currency-column"] = old_currency_column


def test_api_add_entries(app, test_client, tmp_path):
    with app.test_request_context():
        app.preprocess_request()
        old_beancount_file = flask.g.ledger.beancount_file_path
        test_file = tmp_path / "test_file"
        test_file.open("a")
        flask.g.ledger.beancount_file_path = str(test_file)

        data = {
            "entries": [
                {
                    "type": "Transaction",
                    "date": "2017-12-12",
                    "flag": "*",
                    "payee": "Test3",
                    "narration": "",
                    "meta": {},
                    "postings": [
                        {
                            "account": "Assets:US:ETrade:Cash",
                            "amount": "100 USD",
                        },
                        {"account": "Assets:US:ETrade:GLD"},
                    ],
                },
                {
                    "type": "Transaction",
                    "date": "2017-01-12",
                    "flag": "*",
                    "payee": "Test1",
                    "narration": "",
                    "meta": {},
                    "postings": [
                        {
                            "account": "Assets:US:ETrade:Cash",
                            "amount": "100 USD",
                        },
                        {"account": "Assets:US:ETrade:GLD"},
                    ],
                },
                {
                    "type": "Transaction",
                    "date": "2017-02-12",
                    "flag": "*",
                    "payee": "Test",
                    "narration": "Test",
                    "meta": {},
                    "postings": [
                        {
                            "account": "Assets:US:ETrade:Cash",
                            "amount": "100 USD",
                        },
                        {"account": "Assets:US:ETrade:GLD"},
                    ],
                },
            ]
        }
        url = flask.url_for("json_api.add_entries")

        response = test_client.put(
            url, data=flask.json.dumps(data), content_type="application/json"
        )
        assert_api_success(response, "Stored 3 entries.")

        assert (
            test_file.read_text("utf-8")
            == """
2017-01-12 * "Test1" ""
  Assets:US:ETrade:Cash                                 100 USD
  Assets:US:ETrade:GLD

2017-02-12 * "Test" "Test"
  Assets:US:ETrade:Cash                                 100 USD
  Assets:US:ETrade:GLD

2017-12-12 * "Test3" ""
  Assets:US:ETrade:Cash                                 100 USD
  Assets:US:ETrade:GLD
"""
        )

        flask.g.ledger.beancount_file_path = old_beancount_file


@pytest.mark.parametrize(
    "query_string,result_str",
    [
        ("balances from year = 2014", "5086.65 USD"),
        ("nononono", "ERROR: Syntax error near"),
        ("select sum(day)", "43558"),
    ],
)
def test_api_query_result(query_string, result_str, app, test_client) -> None:
    with app.test_request_context():
        app.preprocess_request()
        url = flask.url_for("json_api.query_result", query_string=query_string)

    response = test_client.get(url)
    assert response.status_code == 200
    assert result_str in response.get_data(True)
