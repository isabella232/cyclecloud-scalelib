from __future__ import print_function

import json
import sys
from typing import Any, List, Optional, Set, TextIO, Tuple

from hpc.autoscale.hpctypes import Hostname
from hpc.autoscale.job.demand import DemandResult
from hpc.autoscale.node.node import Node


class DemandPrinter:
    def __init__(
        self,
        column_names: Optional[List[str]] = None,
        stream: Optional[TextIO] = None,
        json: bool = False,
    ) -> None:
        column_names_list: List[str] = []
        if column_names:
            column_names_list = column_names

        self.__defaults = {}

        for n in range(len(column_names_list)):
            expr = column_names_list[n]
            if ":" in expr:
                column, default_value = expr.split(":", 1)
                column_names_list[n] = column
                self.__defaults[column] = default_value

        self.column_names = [x.lower() for x in column_names_list]

        self.stream = stream or sys.stdout
        self.json = json

    def _calc_width(self, columns: List[str], rows: List[List[str]]) -> Tuple[int, ...]:
        maxes = [len(c) for c in columns]
        for row in rows:
            for n in range(len(row)):
                maxes[n] = max(len(row[n]), maxes[n])
        return tuple(maxes)

    def _get_all_columns(self, compute_nodes: List[Node]) -> List[str]:

        columns = []
        for attr_name in dir(Node):
            if not attr_name[0].isalpha():
                continue
            attr = getattr(Node, attr_name)
            if hasattr(attr, "__call__"):
                continue
            columns.append(attr_name)

        if compute_nodes:
            all_available: Set[str] = set()
            for n in compute_nodes:
                all_available.update(n.available.keys())

            columns += list(all_available)
        assert None not in columns
        columns = sorted(columns)
        return columns

    def print_columns(self, demand_result: DemandResult = None) -> None:
        columns = self.column_names
        if not columns:
            columns = self._get_all_columns(
                demand_result.compute_nodes if demand_result else []
            )

        widths = self._calc_width(columns, [])
        formats = " ".join(["{:%d}" % x for x in widths])
        assert len(widths) == len(columns), "{} != {}".format(len(widths), len(columns))
        print(formats.format(*columns), file=self.stream)

    def print_demand(self, demand_result: DemandResult) -> None:
        rows = []
        columns = self.column_names
        if columns == "all":
            columns = self._get_all_columns(demand_result.compute_nodes)

        columns = [c for c in columns if c not in ["available", "node"]]
        columns = ["job_ids" if c == "assigned_job_ids" else c for c in columns]
        if "name" in columns:
            columns.remove("name")
            columns.insert(0, "name")

        for node in demand_result.matched_nodes + demand_result.unmatched_nodes:
            row: List[str] = []
            rows.append(row)
            for column in columns:
                # TODO justify - this is a printing function, so this value could be lots of things etc.

                value: Any = None
                is_from_available = column.startswith("*")
                if is_from_available:
                    column = column[1:]

                if column == "hostname":
                    hostname = node.hostname

                    if not node.exists or not hostname:
                        if node.private_ip:
                            hostname = Hostname(str(node.private_ip))
                        else:
                            hostname = Hostname("tbd")
                    value = hostname
                elif column == "job_ids":
                    value = node.assignments
                elif hasattr(node, column):
                    value = getattr(node, column)
                else:
                    if is_from_available:
                        value = node.available.get(column)
                    else:
                        value = node.resources.get(column)

                if value is None:
                    value = self.__defaults.get(column)

                if isinstance(value, list):
                    value = ",".join(value)
                elif isinstance(value, set):
                    value = ",".join(value)
                elif value is None:
                    value = ""
                elif not isinstance(value, str):
                    value = str(value)
                row.append(value)

        widths = self._calc_width(columns, rows)
        formats = " ".join(["{:%d}" % x for x in widths])
        if self.json:
            json.dump(
                [dict(zip(columns, row)) for row in rows], self.stream, indent=2,
            )
        else:
            print(formats.format(*[c.upper() for c in columns]), file=self.stream)
            for row in rows:
                print(formats.format(*[str(r) for r in row]), file=self.stream)

    def __str__(self) -> str:
        return "DemandPrinter(columns={}, json={}, stream={})".format(
            str(self.column_names), self.json, self.stream
        )

    def __repr__(self) -> str:
        return str(self)


def print_columns(
    demand_result: DemandResult, stream: Optional[TextIO] = None, json: bool = False,
) -> None:
    DemandPrinter(None, stream=stream, json=json).print_columns(demand_result)


def print_demand(
    columns: List[str],
    demand_result: DemandResult,
    stream: Optional[TextIO] = None,
    json: bool = False,
) -> None:
    DemandPrinter(columns, stream=stream, json=json).print_demand(demand_result)
