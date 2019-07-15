#!/usr/bin/env python
import json
import re
# TODO: Replase urllib to requests
from urllib.request import Request, urlopen, HTTPError, URLError
from typing import Dict, Iterator, List

DEFAULT_SOLR_URL = 'http://localhost:8983/solr'
# s/( -?)9\d\.\d{2,}/\190.0/g
REGEX_OUTER_LATITUDE = re.compile(r"(?P<sign> -?)9\d\.\d{2,}")
# s/([\(,]-?)18\d\.\d{2,}/\1180.0/g
REGEX_OUTER_LONGITUDE = re.compile(r"(?P<sign>[\(,]-?)18\d\.\d{2,}")


class SolrClient:
    def __init__(self, core: str, base_url: str = DEFAULT_SOLR_URL):
        self.base_url = base_url
        self.core = core

    def upsert_field_types(self, field_types: Iterator[Dict]) -> List:
        return [self.__upsert_field_type(field_type) for field_type in field_types]

    def __upsert_field_type(self, field_type: Dict):
        url = self.__build_url(suffix="schema")
        upsert_key = self.__switch_upsert_field_type_key(name=field_type['name'])
        data = {upsert_key: field_type}
        headers = {"Content-type": "application/json"}
        req = Request(url, json.dumps(data).encode(), headers)
        try:
            with urlopen(req) as res:
                return res
        except HTTPError as err:
            print(f"Failed to upsert field. {field_type}")
            print(err.code)
            print(err.reason)
            raise err
        except URLError as err:
            print(f"Failed to upsert field. {field_type}")
            print(err.reason)
            raise err

    def __switch_upsert_field_type_key(self, name: str) -> str:
        if self.__exists_field_type(name):
            return "replace-field-type"
        else:
            return "add-field-type"

    def __exists_field_type(self, name: str) -> bool:
        url = self.__build_url(suffix=f"schema/fieldtypes/{name}")
        try:
            with urlopen(Request(url)) as _:
                return True
        except HTTPError as err:
            if err.code == 404:
                return False
            raise err
        except URLError as err:
            raise err

    def __build_url(self, suffix: str) -> str:
        return f"{self.base_url}/{self.core}/{suffix}"

    def upsert_fields(self, fields: Iterator) -> List:
        return [self.__upsert_field(field) for field in fields]

    def __upsert_field(self, field: Dict):
        url = self.__build_url(suffix="schema")
        upsert_key = self.__switch_upsert_field_key(name=field['name'])
        data = {upsert_key: field}
        headers = {"Content-type": "application/json"}
        req = Request(url, json.dumps(data).encode(), headers)
        try:
            with urlopen(req) as res:
                _ = res.read
        except HTTPError as err:
            print(f"Failed to upsert field: {field['name']}")
            print(err.code)
            print(err.reason)
            raise err
        except URLError as err:
            print(f"Failed to upsert field: {field['name']}")
            print(err.reason)
            raise err

    def __switch_upsert_field_key(self, name: str) -> str:
        if self.__exists_field(name):
            return "replace-field"
        else:
            return "add-field"

    def __exists_field(self, name: str) -> bool:
        url = self.__build_url(suffix=f"schema/fields/{name}")
        try:
            with urlopen(Request(url)) as _:
                return True
        except HTTPError as err:
            if err.code == 404:
                return False
            raise err

    def index(self, documents: Iterator[Dict]):
        return [self.__index_document(document) for document in documents]

    def __index_document(self, document: Dict):
        document["WKT"] = rearrange_out_of_range_point(document["WKT"])

        url = self.__build_url(suffix="update/json/docs")
        headers = {"Content-type": "application/json"}
        req = Request(url, json.dumps(document).encode(), headers, method="POST")
        try:
            with urlopen(req) as res:
                _ = res.read()
        except HTTPError as err:
            print(err.code)
            print(err.reason)
            if err.code == 400:
                print(f"[ERROR]: Skipped to index {document['places']}")
                print(err.msg)
                print(json.dumps(document).encode())
                return
            raise err
        except URLError as err:
            print(err.reason)
            raise err
    

    def commit(self):
        url = self.__build_url(suffix="update?commit=true")
        try:
            with urlopen(Request(url)) as res:
                return res
        except HTTPError as err:
            raise err
        except URLError as err:
            raise err

    def delete_all_index(self):
        url = self.__build_url(suffix="update?commit=true")
        headers = {"Content-type": "application/json"}
        data = {"delete": {"query": "*:*"}}
        req = Request(url, json.dumps(data).encode(), headers)
        try:
            with urlopen(req) as res:
                _ = res.read()
        except HTTPError as err:
            print(err.code)
            print(err.reason)
            raise err
        except URLError as err:
            print(err.reason)
            raise err


def rearrange_out_of_range_point(wkt: str) -> str:
    r"""
    Flatten out of range point to on border.
    latitude: [-90.0, 90.0]; longitude: [-180.0, 180.0]

    latitude: 's/( -?)9\d\.\d{2,}/\190.0/g'
    longitude: 's/([\(,]-?)18\d\.\d{2,}/\1180.0/g'
    """
    wkt = REGEX_OUTER_LATITUDE.sub(r"\g<sign>90.0", wkt)
    wkt = REGEX_OUTER_LONGITUDE.sub(r"\g<sign>180.0", wkt)
    return wkt
