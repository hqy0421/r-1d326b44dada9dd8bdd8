"""
pyexcel.questionnaire
~~~~~~~~~~~~~~~~~~~~~

Weighted questionnaire statistics that honour skip (routing) conditions

A questionnaire is described by four tables:

* questions: one row per question, optionally pointing at a parent question
  and at the option(s) of that parent which make the question applicable
* options: the valid options of every question
* respondents: one row per respondent, with a group and a frequency weight
* answers: long format answers, one row per respondent and question

A root question (no parent) is applicable to everybody. A child question is
applicable only when its parent is itself applicable *and* the respondent's
answer to the parent is one of the configured trigger options. Residual
answers left in the source table for a question whose ancestor is inactive
are excluded: they never make the question applicable again.

:copyright: (c) 2014-2026 by C Wang
:license: New BSD License, see LICENSE for more details
"""

import re
from collections import OrderedDict

from pyexcel.book import Book
from pyexcel.exceptions import QuestionnaireError

APPLICABLE_ANSWERS_SHEET = "applicable_answers"
OPTION_DISTRIBUTION_SHEET = "option_distribution"
EXCLUDED_ANSWERS_SHEET = "excluded_answers"

APPLICABLE_ANSWERS_COLUMNS = [
    "respondent",
    "group",
    "weight",
    "question",
    "option",
    "is_missing",
]

OPTION_DISTRIBUTION_COLUMNS = [
    "group",
    "question",
    "option",
    "is_missing",
    "weight",
    "denominator",
    "proportion",
    "applicable_respondents",
]

EXCLUDED_ANSWERS_COLUMNS = [
    "respondent",
    "group",
    "weight",
    "question",
    "option",
    "reason",
]

DEFAULT_COLUMNS = {
    "question": "question",
    "parent": "parent",
    "trigger": "trigger",
    "option": "option",
    "respondent": "respondent",
    "group": "group",
    "weight": "weight",
}

#: the only reason for which an answer is excluded
NOT_APPLICABLE = "not applicable"

_MISSING = object()
_TRIGGER_SEPARATORS = re.compile(r"[,;|]")


def questionnaire_statistics(
    questions,
    options,
    respondents,
    answers,
    columns=None,
):
    """Compute weighted statistics for a questionnaire with skip conditions

    :param questions: the question tree. Each row has a question identifier,
                      an optional parent question identifier and, for child
                      questions, the parent option(s) that trigger the child.
    :param options: the valid options of every question.
    :param respondents: one row per respondent with its group and its
                        positive integer frequency weight.
    :param answers: long format answers: one row per respondent, question and
                    answer. A blank option means the respondent did not
                    answer.
    :param dict columns: optional mapping to rename the expected columns. The
                         keys are ``question``, ``parent``, ``trigger``,
                         ``option``, ``respondent``, ``group`` and ``weight``.

    Each table can be a :class:`pyexcel.Sheet`, a two dimensional array whose
    first row holds the column names, a dictionary of columns or a list of
    records (dictionaries).

    The result is a native :class:`pyexcel.Book` with three sheets:

    ``applicable_answers``
        one row for every applicable respondent and question, with the
        current answer (blank and flagged when missing)
    ``option_distribution``
        for every group and question, the weight and proportion of each
        option plus the missing answers. The denominator is the weight of
        all applicable respondents of the group for that question,
        including the ones who did not answer. When nobody is applicable the
        proportion is left blank.
    ``excluded_answers``
        the residual answers that were not counted because the respondent
        was not applicable to the question

    Duplicate identifiers, invalid options, unknown references and cyclic
    rules raise :class:`pyexcel.exceptions.QuestionnaireError` before any
    result is produced. The source tables and any previous result are never
    modified; a later call reads the current values of the given sheets.

    Example::

        >>> import pyexcel
        >>> questions = [
        ...     ["question", "parent", "trigger"],
        ...     ["q1", "", ""],
        ...     ["q2", "q1", "yes"],
        ... ]
        >>> options = [
        ...     ["question", "option"],
        ...     ["q1", "yes"],
        ...     ["q1", "no"],
        ...     ["q2", "a"],
        ...     ["q2", "b"],
        ... ]
        >>> respondents = [
        ...     ["respondent", "group", "weight"],
        ...     ["r1", "g1", 2],
        ...     ["r2", "g1", 1],
        ... ]
        >>> answers = [
        ...     ["respondent", "question", "option"],
        ...     ["r1", "q1", "yes"],
        ...     ["r1", "q2", "a"],
        ...     ["r2", "q1", "no"],
        ...     ["r2", "q2", "b"],
        ... ]
        >>> book = pyexcel.questionnaire_statistics(
        ...     questions, options, respondents, answers
        ... )
        >>> book.sheet_names()
        ['applicable_answers', 'option_distribution', 'excluded_answers']
        >>> for row in book["option_distribution"].to_array()[1:]:
        ...     print(row)
        ['g1', 'q1', 'yes', 0, 2, 3, 0.6666666666666666, 2]
        ['g1', 'q1', 'no', 0, 1, 3, 0.3333333333333333, 2]
        ['g1', 'q1', '', 1, 0, 3, 0.0, 2]
        ['g1', 'q2', 'a', 0, 2, 2, 1.0, 1]
        ['g1', 'q2', 'b', 0, 0, 2, 0.0, 1]
        ['g1', 'q2', '', 1, 0, 2, 0.0, 1]
    """
    table_columns = dict(DEFAULT_COLUMNS)
    if columns:
        unknown = set(columns) - set(DEFAULT_COLUMNS)
        if unknown:
            raise QuestionnaireError(
                "Unknown column mapping(s): %s"
                % ", ".join(sorted(str(key) for key in unknown))
            )
        table_columns.update(columns)

    question_data = _QuestionData(questions, table_columns)
    option_data = _OptionData(options, table_columns)
    respondent_data = _RespondentData(respondents, table_columns)
    answer_data = _AnswerData(answers, table_columns)

    return _build_book(
        question_data,
        option_data,
        respondent_data,
        answer_data,
    )


def _build_book(questions, options, respondents, answers):
    """Validate the questionnaire and build the resulting book"""
    questions.validate(option_data=options)
    options.validate(question_data=questions)
    answers.validate(
        questions=questions, options=options, respondents=respondents
    )

    order = questions.topological_order()
    respondents.compute_applicability(questions, order, answers)

    applicable_rows = _applicable_rows(questions, respondents, answers)
    distribution_rows = _distribution_rows(
        questions, options, respondents, answers
    )
    excluded_rows = _excluded_rows(questions, respondents, answers)

    sheets = OrderedDict()
    sheets[APPLICABLE_ANSWERS_SHEET] = [
        list(APPLICABLE_ANSWERS_COLUMNS)
    ] + applicable_rows
    sheets[OPTION_DISTRIBUTION_SHEET] = [
        list(OPTION_DISTRIBUTION_COLUMNS)
    ] + distribution_rows
    sheets[EXCLUDED_ANSWERS_SHEET] = [
        list(EXCLUDED_ANSWERS_COLUMNS)
    ] + excluded_rows
    return Book(sheets)


def _applicable_rows(questions, respondents, answers):
    rows = []
    for respondent in respondents:
        applicable = respondent["applicable"]
        for question in questions:
            if not applicable[question["key"]]:
                continue
            answer = answers.get(respondent["key"], question["key"])
            if answer is _MISSING:
                rows.append(
                    [
                        respondent["value"],
                        respondent["group_value"],
                        respondent["weight"],
                        question["value"],
                        "",
                        1,
                    ]
                )
            else:
                rows.append(
                    [
                        respondent["value"],
                        respondent["group_value"],
                        respondent["weight"],
                        question["value"],
                        answer["option_value"],
                        0,
                    ]
                )
    return rows


def _distribution_rows(questions, options, respondents, answers):
    rows = []
    for group in respondents.groups():
        members = respondents.members_of(group)
        for question in questions:
            question_key = question["key"]
            applicable_members = [
                member
                for member in members
                if member["applicable"][question_key]
            ]
            denominator = sum(
                member["weight"] for member in applicable_members
            )
            applicable_count = len(applicable_members)

            option_weights = OrderedDict(
                (option["key"], 0) for option in options.of(question_key)
            )
            missing_weight = 0
            for member in applicable_members:
                answer = answers.get(member["key"], question_key)
                if answer is _MISSING:
                    missing_weight += member["weight"]
                else:
                    option_weights[answer["option_key"]] += member["weight"]

            for option_key, weight in option_weights.items():
                option = options.get(question_key, option_key)
                rows.append(
                    [
                        group["value"],
                        question["value"],
                        option["value"],
                        0,
                        weight,
                        denominator,
                        _proportion(weight, denominator),
                        applicable_count,
                    ]
                )
            rows.append(
                [
                    group["value"],
                    question["value"],
                    "",
                    1,
                    missing_weight,
                    denominator,
                    _proportion(missing_weight, denominator),
                    applicable_count,
                ]
            )
    return rows


def _excluded_rows(questions, respondents, answers):
    rows = []
    for answer in answers:
        respondent = respondents.get(answer["respondent_key"])
        question = questions.get(answer["question_key"])
        if respondent["applicable"][question["key"]]:
            continue
        rows.append(
            [
                respondent["value"],
                respondent["group_value"],
                respondent["weight"],
                question["value"],
                _display_option(answer),
                NOT_APPLICABLE,
            ]
        )
    return rows


def _proportion(weight, denominator):
    if denominator == 0:
        return ""
    return weight / denominator


def _display_option(answer):
    return answer["option_value"]


class _Table(object):
    """Common behaviour of a named input table"""

    name = "table"
    required = ()

    def __init__(self, table, columns):
        headers, rows = _coerce_table(table, self.name)
        self._headers = headers
        self._rows = rows
        self._columns = columns
        self._check_required()

    def _check_required(self):
        if not self._headers and not self._rows:
            # an entirely empty table is allowed; it just contributes nothing
            return
        for role in self.required:
            if self._columns[role] not in self._headers:
                raise QuestionnaireError(
                    "The %s table has no '%s' column"
                    % (self.name, self._columns[role])
                )

    def _column_index(self, role):
        name = self._columns[role]
        if name not in self._headers:
            return -1
        return self._headers.index(name)

    def _value(self, row, role):
        index = self._column_index(role)
        if index < 0:
            return ""
        return row[index]

    def _rows_with_data(self):
        for number, row in enumerate(self._rows, start=2):
            if all(_is_blank(value) for value in row):
                continue
            yield number, row


class _QuestionData(_Table):
    name = "questions"
    required = ("question",)

    def __init__(self, table, columns):
        _Table.__init__(self, table, columns)
        self._items = []
        self._by_key = OrderedDict()
        self._load()

    def _load(self):
        for _, row in self._rows_with_data():
            value = self._value(row, "question")
            if _is_blank(value):
                raise QuestionnaireError(
                    "Missing question identifier in the questions table"
                )
            key = _key(value)
            if key in self._by_key:
                raise QuestionnaireError(
                    "Duplicate question identifier '%s'" % (value,)
                )
            item = {
                "key": key,
                "value": value,
                "parent_key": None,
                "triggers": [],
            }
            parent = self._value(row, "parent")
            if not _is_blank(parent):
                item["parent_key"] = _key(parent)
            triggers = _trigger_values(self._value(row, "trigger"))
            if item["parent_key"] is None and triggers:
                raise QuestionnaireError(
                    "Question '%s' has a trigger but no parent" % (value,)
                )
            if item["parent_key"] is not None and not triggers:
                raise QuestionnaireError(
                    "Child question '%s' has no trigger option" % (value,)
                )
            item["triggers"] = triggers
            item["trigger_keys"] = set(trigger["key"] for trigger in triggers)
            self._items.append(item)
            self._by_key[key] = item

    def __iter__(self):
        return iter(self._items)

    def get(self, key):
        return self._by_key[key]

    def validate(self, option_data):
        for item in self._items:
            parent_key = item["parent_key"]
            if parent_key is None:
                continue
            if parent_key == item["key"]:
                raise QuestionnaireError(
                    "Question '%s' cannot be its own parent" % (item["value"],)
                )
            if parent_key not in self._by_key:
                raise QuestionnaireError(
                    "Unknown parent question '%s' for question '%s'"
                    % (item["parent_key"], item["value"])
                )
            parent_options = set(
                option["key"] for option in option_data.of(parent_key)
            )
            for trigger in item["triggers"]:
                if trigger["key"] not in parent_options:
                    raise QuestionnaireError(
                        "Trigger option '%s' is not a valid option of "
                        "parent question '%s'"
                        % (trigger["value"], self._by_key[parent_key]["value"])
                    )

    def topological_order(self):
        """Return the questions, parents before children

        Cyclic rules are rejected here.
        """
        order = []
        ready = [item for item in self._items if item["parent_key"] is None]
        children = OrderedDict((item["key"], []) for item in self._items)
        for item in self._items:
            if item["parent_key"] is not None:
                children[item["parent_key"]].append(item)
        while ready:
            item = ready.pop(0)
            order.append(item)
            for child in children[item["key"]]:
                ready.append(child)
        if len(order) != len(self._items):
            ordered = set(item["key"] for item in order)
            involved = [
                str(item["value"])
                for item in self._items
                if item["key"] not in ordered
            ]
            raise QuestionnaireError(
                "Cyclic question rule(s): %s" % ", ".join(involved)
            )
        return order


class _OptionData(_Table):
    name = "options"
    required = ("question", "option")

    def __init__(self, table, columns):
        _Table.__init__(self, table, columns)
        self._items = []
        self._by_key = OrderedDict()
        self._by_question = OrderedDict()
        self._load()

    def _load(self):
        for _, row in self._rows_with_data():
            question = self._value(row, "question")
            option = self._value(row, "option")
            if _is_blank(question) or _is_blank(option):
                raise QuestionnaireError(
                    "Each option row needs a question and an option"
                )
            question_key = _key(question)
            option_key = _key(option)
            pair = (question_key, option_key)
            if pair in self._by_key:
                raise QuestionnaireError(
                    "Duplicate option '%s' for question '%s'"
                    % (option, question)
                )
            item = {
                "question_key": question_key,
                "key": option_key,
                "value": option,
            }
            self._items.append(item)
            self._by_key[pair] = item
            self._by_question.setdefault(question_key, []).append(item)

    def of(self, question_key):
        return self._by_question.get(question_key, [])

    def get(self, question_key, option_key):
        return self._by_key[(question_key, option_key)]

    def validate(self, question_data):
        for item in self._items:
            if item["question_key"] not in question_data._by_key:
                raise QuestionnaireError(
                    "Option '%s' refers to unknown question '%s'"
                    % (item["value"], item["question_key"])
                )


class _RespondentData(_Table):
    name = "respondents"
    required = ("respondent", "weight")

    def __init__(self, table, columns):
        _Table.__init__(self, table, columns)
        self._items = []
        self._by_key = OrderedDict()
        self._groups = OrderedDict()
        self._load()

    def _load(self):
        for number, row in self._rows_with_data():
            value = self._value(row, "respondent")
            if _is_blank(value):
                raise QuestionnaireError(
                    "Missing respondent identifier in row %s" % (number,)
                )
            key = _key(value)
            if key in self._by_key:
                raise QuestionnaireError(
                    "Duplicate respondent identifier '%s'" % (value,)
                )
            weight = _positive_integer(self._value(row, "weight"), value)
            group_value = self._value(row, "group")
            if _is_blank(group_value):
                group_value = ""
            group_key = _key(group_value)
            item = {
                "key": key,
                "value": value,
                "weight": weight,
                "group_key": group_key,
                "group_value": group_value,
                "applicable": {},
            }
            self._items.append(item)
            self._by_key[key] = item
            if group_key not in self._groups:
                self._groups[group_key] = {
                    "key": group_key,
                    "value": group_value,
                    "members": [],
                }
            self._groups[group_key]["members"].append(item)

    def __iter__(self):
        return iter(self._items)

    def get(self, key):
        return self._by_key[key]

    def groups(self):
        return list(self._groups.values())

    def members_of(self, group):
        return group["members"]

    def compute_applicability(self, questions, order, answers):
        for respondent in self._items:
            applicable = respondent["applicable"]
            respondent_key = respondent["key"]
            for question in order:
                question_key = question["key"]
                parent_key = question["parent_key"]
                if parent_key is None:
                    applicable[question_key] = True
                elif not applicable[parent_key]:
                    applicable[question_key] = False
                else:
                    answer = answers.get(respondent_key, parent_key)
                    hidden = answer is _MISSING or (
                        answer["option_key"] not in question["trigger_keys"]
                    )
                    applicable[question_key] = not hidden


class _AnswerData(_Table):
    name = "answers"
    required = ("respondent", "question")

    def __init__(self, table, columns):
        _Table.__init__(self, table, columns)
        self._items = []
        self._by_key = OrderedDict()
        self._seen = set()
        self._load()

    def _load(self):
        for _, row in self._rows_with_data():
            respondent = self._value(row, "respondent")
            question = self._value(row, "question")
            if _is_blank(respondent) or _is_blank(question):
                raise QuestionnaireError(
                    "Each answer row needs a respondent and a question"
                )
            respondent_key = _key(respondent)
            question_key = _key(question)
            pair = (respondent_key, question_key)
            if pair in self._seen:
                raise QuestionnaireError(
                    "Duplicate answer for respondent '%s' and question '%s'"
                    % (respondent, question)
                )
            self._seen.add(pair)
            option = self._value(row, "option")
            if _is_blank(option):
                # an empty answer means the respondent did not answer; it is
                # not a residual record, so it is simply left out
                continue
            item = {
                "respondent_key": respondent_key,
                "question_key": question_key,
                "option_key": _key(option),
                "option_value": option,
            }
            self._items.append(item)
            self._by_key[pair] = item

    def __iter__(self):
        return iter(self._items)

    def get(self, respondent_key, question_key):
        return self._by_key.get((respondent_key, question_key), _MISSING)

    def validate(self, questions, options, respondents):
        for item in self._items:
            respondent_key = item["respondent_key"]
            question_key = item["question_key"]
            if respondent_key not in respondents._by_key:
                raise QuestionnaireError(
                    "Answer for unknown respondent '%s'" % (respondent_key,)
                )
            if question_key not in questions._by_key:
                raise QuestionnaireError(
                    "Answer for unknown question '%s'" % (question_key,)
                )
            option_key = item["option_key"]
            valid = set(
                declared["key"] for declared in options.of(question_key)
            )
            if option_key not in valid:
                raise QuestionnaireError(
                    "Invalid option '%s' for question '%s'"
                    % (
                        item["option_value"],
                        questions.get(question_key)["value"],
                    )
                )
            declared = options.get(question_key, option_key)
            item["option_value"] = declared["value"]


def _trigger_values(value):
    triggers = []
    if _is_blank(value):
        return triggers
    if isinstance(value, (list, tuple, set)):
        tokens = list(value)
    else:
        tokens = _TRIGGER_SEPARATORS.split(str(value))
    for token in tokens:
        if _is_blank(token):
            continue
        triggers.append({"key": _key(token), "value": token})
    # keep the first declaration for each trigger
    unique = OrderedDict()
    for trigger in triggers:
        unique.setdefault(trigger["key"], trigger)
    return list(unique.values())


def _coerce_table(table, name):
    """Return (headers, rows) from any accepted table representation"""
    if hasattr(table, "to_array"):
        return _from_sheet(table, name)

    if isinstance(table, dict):
        headers = [str(key).strip() for key in table.keys()]
        columns = [list(value) for value in table.values()]
        if len(set(map(len, columns))) > 1:
            raise QuestionnaireError(
                "The columns of the %s table have different lengths" % name
            )
        rows = [list(row) for row in zip(*columns)] if columns else []
        return _normalise_headers(headers, name), rows

    if isinstance(table, (list, tuple)):
        if len(table) == 0:
            return [], []
        if isinstance(table[0], dict):
            headers = []
            for record in table:
                for key in record.keys():
                    key = str(key).strip()
                    if key not in headers:
                        headers.append(key)
            rows = [
                [record.get(header, "") for header in headers]
                for record in table
            ]
            return _normalise_headers(headers, name), rows
        rows = [list(row) for row in table]
        return _split_header(rows, name)

    raise QuestionnaireError(
        "The %s table must be a Sheet, an array, a dictionary or records"
        % name
    )


def _from_sheet(table, name):
    """Read the data of a sheet together with its column names

    A questionnaire table is addressed by column names only, so the row
    names of a sheet are not part of the data.
    """
    headers = _normalise_headers(
        list(getattr(table, "colnames", []) or []), name
    )
    if hasattr(table, "rows"):
        rows = [list(row) for row in table.rows()]
        embedded_headers = False
    else:
        rows = [list(row) for row in table.to_array()]
        embedded_headers = True
    return _apply_headers(headers, rows, name, embedded_headers)


def _apply_headers(headers, rows, name, embedded_headers=False):
    """Align data rows with already known column names

    A sheet may keep its column names separately from the data (as
    ``name_columns_by_row`` does) while ``to_array`` still puts them back as
    the first row. That first row is dropped when it repeats the names.
    """
    if not headers:
        return _split_header(rows, name)
    if embedded_headers and rows and _header_row(rows[0]) == headers:
        rows = rows[1:]
    return _normalise_headers(headers, name), _align_rows(rows, headers, name)


def _header_row(row):
    return [_header_text(value) for value in row]


def _header_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _split_header(rows, name):
    if not rows:
        return [], []
    headers = _normalise_headers(list(rows[0]), name)
    return headers, _align_rows(rows[1:], headers, name)


def _align_rows(rows, headers, name):
    aligned = []
    for number, row in enumerate(rows, start=2):
        row = list(row)
        if len(row) > len(headers):
            raise QuestionnaireError(
                "Row %s of the %s table has more values than columns"
                % (number, name)
            )
        if len(row) < len(headers):
            row.extend([""] * (len(headers) - len(row)))
        aligned.append(row)
    return aligned


def _normalise_headers(headers, name):
    normalised = []
    for header in headers:
        if header is None:
            header = ""
        header = str(header).strip()
        if header in normalised:
            raise QuestionnaireError(
                "Duplicate column '%s' in the %s table" % (header, name)
            )
        normalised.append(header)
    return normalised


def _positive_integer(value, respondent):
    if isinstance(value, bool):
        raise QuestionnaireError(
            "The weight of respondent '%s' is not a positive integer"
            % (respondent,)
        )
    if isinstance(value, int):
        number = value
    elif isinstance(value, float):
        if not value.is_integer():
            raise QuestionnaireError(
                "The weight of respondent '%s' is not a positive integer"
                % (respondent,)
            )
        number = int(value)
    elif isinstance(value, str):
        text = value.strip()
        if not re.fullmatch(r"[+]?\d+", text):
            raise QuestionnaireError(
                "The weight of respondent '%s' is not a positive integer"
                % (respondent,)
            )
        number = int(text)
    else:
        raise QuestionnaireError(
            "The weight of respondent '%s' is not a positive integer"
            % (respondent,)
        )
    if number <= 0:
        raise QuestionnaireError(
            "The weight of respondent '%s' is not a positive integer"
            % (respondent,)
        )
    return number


def _is_blank(value):
    return value is None or (isinstance(value, str) and value.strip() == "")


def _key(value):
    """Normalise an identifier so that 1, 1.0 and "1" mean the same cell"""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()
