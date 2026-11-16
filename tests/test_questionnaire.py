import unittest

import pyexcel as pe
from pyexcel.exceptions import QuestionnaireError

from .nose_tools import eq_, raises

QUESTIONS = [
    ["question", "parent", "trigger"],
    ["q1", "", ""],
    ["q2", "q1", "yes"],
    ["q3", "q2", "a"],
]

OPTIONS = [
    ["question", "option"],
    ["q1", "yes"],
    ["q1", "no"],
    ["q2", "a"],
    ["q2", "b"],
    ["q3", "x"],
    ["q3", "y"],
]

RESPONDENTS = [
    ["respondent", "group", "weight"],
    ["r1", "g1", 2],
    ["r2", "g1", 1],
    ["r3", "g2", 3],
]

ANSWERS = [
    ["respondent", "question", "option"],
    ["r1", "q1", "yes"],
    ["r1", "q2", "a"],
    ["r1", "q3", "x"],
    ["r2", "q1", "no"],
    ["r2", "q2", "b"],
    ["r2", "q3", "y"],
    ["r3", "q1", "yes"],
    ["r3", "q2", "b"],
    ["r3", "q3", "x"],
]


def statistics(**overrides):
    parameters = {
        "questions": QUESTIONS,
        "options": OPTIONS,
        "respondents": RESPONDENTS,
        "answers": ANSWERS,
    }
    parameters.update(overrides)
    return pe.questionnaire_statistics(**parameters)


def rows(sheet):
    return sheet.to_array()[1:]


class TestQuestionnaireStatistics(unittest.TestCase):
    def test_result_is_a_native_book_with_three_sheets(self):
        book = statistics()
        assert isinstance(book, pe.Book)
        eq_(
            book.sheet_names(),
            ["applicable_answers", "option_distribution", "excluded_answers"],
        )

    def test_applicable_answers_exclude_residual_answers(self):
        book = statistics()
        detail = rows(book["applicable_answers"])
        eq_(
            detail,
            [
                ["r1", "g1", 2, "q1", "yes", 0],
                ["r1", "g1", 2, "q2", "a", 0],
                ["r1", "g1", 2, "q3", "x", 0],
                ["r2", "g1", 1, "q1", "no", 0],
                ["r3", "g2", 3, "q1", "yes", 0],
                ["r3", "g2", 3, "q2", "b", 0],
            ],
        )

    def test_inactive_ancestor_cannot_be_reactivated(self):
        book = statistics()
        excluded = rows(book["excluded_answers"])
        eq_(
            excluded,
            [
                ["r2", "g1", 1, "q2", "b", "not applicable"],
                ["r2", "g1", 1, "q3", "y", "not applicable"],
                ["r3", "g2", 3, "q3", "x", "not applicable"],
            ],
        )

    def test_distribution_uses_applicable_weights_as_denominator(self):
        book = statistics()
        distribution = rows(book["option_distribution"])
        eq_(
            distribution,
            [
                ["g1", "q1", "yes", 0, 2, 3, 2 / 3, 2],
                ["g1", "q1", "no", 0, 1, 3, 1 / 3, 2],
                ["g1", "q1", "", 1, 0, 3, 0.0, 2],
                ["g1", "q2", "a", 0, 2, 2, 1.0, 1],
                ["g1", "q2", "b", 0, 0, 2, 0.0, 1],
                ["g1", "q2", "", 1, 0, 2, 0.0, 1],
                ["g1", "q3", "x", 0, 2, 2, 1.0, 1],
                ["g1", "q3", "y", 0, 0, 2, 0.0, 1],
                ["g1", "q3", "", 1, 0, 2, 0.0, 1],
                ["g2", "q1", "yes", 0, 3, 3, 1.0, 1],
                ["g2", "q1", "no", 0, 0, 3, 0.0, 1],
                ["g2", "q1", "", 1, 0, 3, 0.0, 1],
                ["g2", "q2", "a", 0, 0, 3, 0.0, 1],
                ["g2", "q2", "b", 0, 3, 3, 1.0, 1],
                ["g2", "q2", "", 1, 0, 3, 0.0, 1],
                ["g2", "q3", "x", 0, 0, 0, "", 0],
                ["g2", "q3", "y", 0, 0, 0, "", 0],
                ["g2", "q3", "", 1, 0, 0, "", 0],
            ],
        )

    def test_missing_answer_is_in_the_denominator(self):
        respondents = [
            ["respondent", "group", "weight"],
            ["r1", "g1", 2],
            ["r2", "g1", 3],
        ]
        answers = [
            ["respondent", "question", "option"],
            ["r1", "q1", "yes"],
        ]
        book = statistics(
            questions=[["question", "parent", "trigger"], ["q1", "", ""]],
            options=[["question", "option"], ["q1", "yes"], ["q1", "no"]],
            respondents=respondents,
            answers=answers,
        )
        eq_(
            rows(book["applicable_answers"]),
            [
                ["r1", "g1", 2, "q1", "yes", 0],
                ["r2", "g1", 3, "q1", "", 1],
            ],
        )
        eq_(
            rows(book["option_distribution"]),
            [
                ["g1", "q1", "yes", 0, 2, 5, 0.4, 2],
                ["g1", "q1", "no", 0, 0, 5, 0.0, 2],
                ["g1", "q1", "", 1, 3, 5, 0.6, 2],
            ],
        )

    def test_multiple_trigger_options(self):
        questions = [
            ["question", "parent", "trigger"],
            ["q1", "", ""],
            ["q2", "q1", "yes;maybe"],
        ]
        options = [
            ["question", "option"],
            ["q1", "yes"],
            ["q1", "no"],
            ["q1", "maybe"],
            ["q2", "a"],
        ]
        respondents = [
            ["respondent", "group", "weight"],
            ["r1", "g1", 1],
            ["r2", "g1", 1],
            ["r3", "g1", 1],
        ]
        answers = [
            ["respondent", "question", "option"],
            ["r1", "q1", "yes"],
            ["r2", "q1", "maybe"],
            ["r3", "q1", "no"],
        ]
        book = statistics(
            questions=questions,
            options=options,
            respondents=respondents,
            answers=answers,
        )
        eq_(
            rows(book["option_distribution"]),
            [
                ["g1", "q1", "yes", 0, 1, 3, 1 / 3, 3],
                ["g1", "q1", "no", 0, 1, 3, 1 / 3, 3],
                ["g1", "q1", "maybe", 0, 1, 3, 1 / 3, 3],
                ["g1", "q1", "", 1, 0, 3, 0.0, 3],
                ["g1", "q2", "a", 0, 0, 2, 0.0, 2],
                ["g1", "q2", "", 1, 2, 2, 1.0, 2],
            ],
        )

    def test_groups_are_independent(self):
        book = statistics()
        distribution = rows(book["option_distribution"])
        group2 = [row for row in distribution if row[0] == "g2"]
        eq_(len(group2), 9)

    def test_blank_proportion_when_nobody_is_applicable(self):
        respondents = [
            ["respondent", "group", "weight"],
            ["r1", "g1", 2],
        ]
        answers = [
            ["respondent", "question", "option"],
            ["r1", "q1", "no"],
            ["r1", "q2", "a"],
        ]
        book = statistics(respondents=respondents, answers=answers)
        q2_rows = [
            row for row in rows(book["option_distribution"]) if row[1] == "q2"
        ]
        eq_(
            q2_rows,
            [
                ["g1", "q2", "a", 0, 0, 0, "", 0],
                ["g1", "q2", "b", 0, 0, 0, "", 0],
                ["g1", "q2", "", 1, 0, 0, "", 0],
            ],
        )
        eq_(
            rows(book["excluded_answers"]),
            [["r1", "g1", 2, "q2", "a", "not applicable"]],
        )

    def test_inactive_ancestor_blocks_a_matching_residual_answer(self):
        """A residual answer that matches the trigger still cannot revive it"""
        respondents = [
            ["respondent", "group", "weight"],
            ["r1", "g1", 2],
        ]
        questions = [
            ["question", "parent", "trigger"],
            ["q1", "", ""],
            ["q2", "q1", "yes"],
            ["q3", "q2", "a"],
        ]
        options = [
            ["question", "option"],
            ["q1", "yes"],
            ["q1", "no"],
            ["q2", "a"],
            ["q3", "x"],
        ]
        answers = [
            ["respondent", "question", "option"],
            ["r1", "q1", "no"],
            ["r1", "q2", "a"],
            ["r1", "q3", "x"],
        ]
        book = pe.questionnaire_statistics(
            questions, options, respondents, answers
        )
        eq_(
            rows(book["applicable_answers"]),
            [["r1", "g1", 2, "q1", "no", 0]],
        )
        eq_(
            rows(book["excluded_answers"]),
            [
                ["r1", "g1", 2, "q2", "a", "not applicable"],
                ["r1", "g1", 2, "q3", "x", "not applicable"],
            ],
        )

    def test_source_sheets_are_not_modified(self):
        questions = pe.Sheet(
            [
                ["question", "parent", "trigger"],
                ["q1", "", ""],
                ["q2", "q1", "yes"],
            ]
        )
        options = pe.Sheet(
            [
                ["question", "option"],
                ["q1", "yes"],
                ["q1", "no"],
                ["q2", "a"],
            ]
        )
        respondents = pe.Sheet(
            [["respondent", "group", "weight"], ["r1", "g1", 1]]
        )
        answers = pe.Sheet(
            [
                ["respondent", "question", "option"],
                ["r1", "q1", "yes"],
                ["r1", "q2", "a"],
            ]
        )
        before = [
            sheet.to_array()
            for sheet in [questions, options, respondents, answers]
        ]
        book = pe.questionnaire_statistics(
            questions, options, respondents, answers
        )
        after = [
            sheet.to_array()
            for sheet in [questions, options, respondents, answers]
        ]
        eq_(before, after)
        eq_(
            rows(book["applicable_answers"]),
            [["r1", "g1", 1, "q1", "yes", 0], ["r1", "g1", 1, "q2", "a", 0]],
        )

    def test_recalculation_uses_the_current_values(self):
        respondents = pe.Sheet(
            [["respondent", "group", "weight"], ["r1", "g1", 1]]
        )
        questions = [
            ["question", "parent", "trigger"],
            ["q1", "", ""],
        ]
        options = [["question", "option"], ["q1", "yes"], ["q1", "no"]]
        answers = pe.Sheet(
            [["respondent", "question", "option"], ["r1", "q1", "no"]]
        )
        first = pe.questionnaire_statistics(
            questions, options, respondents, answers
        )
        eq_(
            rows(first["option_distribution"]),
            [
                ["g1", "q1", "yes", 0, 0, 1, 0.0, 1],
                ["g1", "q1", "no", 0, 1, 1, 1.0, 1],
                ["g1", "q1", "", 1, 0, 1, 0.0, 1],
            ],
        )
        answers[1, 2] = "yes"
        second = pe.questionnaire_statistics(
            questions, options, respondents, answers
        )
        eq_(
            rows(second["option_distribution"]),
            [
                ["g1", "q1", "yes", 0, 1, 1, 1.0, 1],
                ["g1", "q1", "no", 0, 0, 1, 0.0, 1],
                ["g1", "q1", "", 1, 0, 1, 0.0, 1],
            ],
        )
        eq_(
            rows(first["option_distribution"]),
            [
                ["g1", "q1", "yes", 0, 0, 1, 0.0, 1],
                ["g1", "q1", "no", 0, 1, 1, 1.0, 1],
                ["g1", "q1", "", 1, 0, 1, 0.0, 1],
            ],
        )

    def test_accepts_sheets_with_column_names(self):
        questions = pe.Sheet(
            [
                ["question", "parent", "trigger"],
                ["q1", "", ""],
                ["q2", "q1", "yes"],
            ],
            name_columns_by_row=0,
        )
        options = pe.Sheet(
            [
                ["question", "option"],
                ["q1", "yes"],
                ["q1", "no"],
                ["q2", "a"],
            ],
            name_columns_by_row=0,
        )
        respondents = pe.Sheet(
            [["respondent", "group", "weight"], ["r1", "g1", 2]],
            name_columns_by_row=0,
        )
        answers = pe.Sheet(
            [
                ["respondent", "question", "option"],
                ["r1", "q1", "yes"],
                ["r1", "q2", "a"],
            ],
            name_columns_by_row=0,
        )
        book = pe.questionnaire_statistics(
            questions, options, respondents, answers
        )
        eq_(
            rows(book["applicable_answers"]),
            [["r1", "g1", 2, "q1", "yes", 0], ["r1", "g1", 2, "q2", "a", 0]],
        )

    def test_accepts_dictionary_and_record_tables(self):
        questions = {
            "question": ["q1", "q2"],
            "parent": ["", "q1"],
            "trigger": ["", "yes"],
        }
        options = [{"question": "q1", "option": "yes"}]
        options.append({"question": "q1", "option": "no"})
        options.append({"question": "q2", "option": "a"})
        respondents = {"respondent": ["r1"], "group": ["g1"], "weight": [4]}
        answers = [
            {"respondent": "r1", "question": "q1", "option": "yes"},
            {"respondent": "r1", "question": "q2", "option": "a"},
        ]
        book = pe.questionnaire_statistics(
            questions, options, respondents, answers
        )
        eq_(
            rows(book["option_distribution"]),
            [
                ["g1", "q1", "yes", 0, 4, 4, 1.0, 1],
                ["g1", "q1", "no", 0, 0, 4, 0.0, 1],
                ["g1", "q1", "", 1, 0, 4, 0.0, 1],
                ["g1", "q2", "a", 0, 4, 4, 1.0, 1],
                ["g1", "q2", "", 1, 0, 4, 0.0, 1],
            ],
        )

    def test_columns_can_be_renamed(self):
        questions = [
            ["题号", "父题", "触发选项"],
            ["q1", "", ""],
            ["q2", "q1", "yes"],
        ]
        options = [
            ["题号", "选项"],
            ["q1", "yes"],
            ["q1", "no"],
            ["q2", "a"],
        ]
        respondents = [["受访者", "分组", "权重"], ["r1", "g1", 1]]
        answers = [
            ["受访者", "题号", "选项"],
            ["r1", "q1", "yes"],
            ["r1", "q2", "a"],
        ]
        book = pe.questionnaire_statistics(
            questions,
            options,
            respondents,
            answers,
            columns={
                "question": "题号",
                "parent": "父题",
                "trigger": "触发选项",
                "option": "选项",
                "respondent": "受访者",
                "group": "分组",
                "weight": "权重",
            },
        )
        eq_(
            rows(book["applicable_answers"]),
            [["r1", "g1", 1, "q1", "yes", 0], ["r1", "g1", 1, "q2", "a", 0]],
        )

    def test_weight_may_be_given_as_numeric_text(self):
        respondents = [["respondent", "group", "weight"], ["r1", "g1", "5"]]
        book = statistics(
            questions=[["question", "parent", "trigger"], ["q1", "", ""]],
            options=[["question", "option"], ["q1", "yes"]],
            respondents=respondents,
            answers=[
                ["respondent", "question", "option"],
                ["r1", "q1", "yes"],
            ],
        )
        eq_(
            rows(book["option_distribution"])[0],
            ["g1", "q1", "yes", 0, 5, 5, 1.0, 1],
        )

    @raises(QuestionnaireError)
    def test_duplicate_respondent_is_rejected(self):
        respondents = [
            ["respondent", "group", "weight"],
            ["r1", "g1", 1],
            ["r1", "g1", 2],
        ]
        statistics(respondents=respondents)

    @raises(QuestionnaireError)
    def test_duplicate_question_is_rejected(self):
        questions = [
            ["question", "parent", "trigger"],
            ["q1", "", ""],
            ["q1", "", ""],
        ]
        statistics(questions=questions)

    @raises(QuestionnaireError)
    def test_duplicate_answer_is_rejected(self):
        answers = [
            ["respondent", "question", "option"],
            ["r1", "q1", "yes"],
            ["r1", "q1", "no"],
        ]
        statistics(answers=answers)

    @raises(QuestionnaireError)
    def test_invalid_option_is_rejected(self):
        answers = [
            ["respondent", "question", "option"],
            ["r1", "q1", "unknown"],
        ]
        statistics(answers=answers)

    @raises(QuestionnaireError)
    def test_unknown_question_in_answers_is_rejected(self):
        answers = [
            ["respondent", "question", "option"],
            ["r1", "q404", "yes"],
        ]
        statistics(answers=answers)

    @raises(QuestionnaireError)
    def test_unknown_respondent_in_answers_is_rejected(self):
        answers = [
            ["respondent", "question", "option"],
            ["r404", "q1", "yes"],
        ]
        statistics(answers=answers)

    @raises(QuestionnaireError)
    def test_invalid_trigger_is_rejected(self):
        questions = [
            ["question", "parent", "trigger"],
            ["q1", "", ""],
            ["q2", "q1", "unknown"],
        ]
        statistics(questions=questions)

    @raises(QuestionnaireError)
    def test_unknown_parent_is_rejected(self):
        questions = [
            ["question", "parent", "trigger"],
            ["q1", "q404", "yes"],
        ]
        statistics(questions=questions)

    @raises(QuestionnaireError)
    def test_cycle_is_rejected(self):
        questions = [
            ["question", "parent", "trigger"],
            ["q1", "q2", "yes"],
            ["q2", "q1", "yes"],
        ]
        options = [
            ["question", "option"],
            ["q1", "yes"],
            ["q2", "yes"],
        ]
        answers = [["respondent", "question", "option"]]
        statistics(questions=questions, options=options, answers=answers)

    @raises(QuestionnaireError)
    def test_self_parent_is_rejected(self):
        questions = [
            ["question", "parent", "trigger"],
            ["q1", "q1", "yes"],
        ]
        statistics(questions=questions)

    @raises(QuestionnaireError)
    def test_zero_weight_is_rejected(self):
        respondents = [["respondent", "group", "weight"], ["r1", "g1", 0]]
        statistics(respondents=respondents)

    @raises(QuestionnaireError)
    def test_negative_weight_is_rejected(self):
        respondents = [["respondent", "group", "weight"], ["r1", "g1", -2]]
        statistics(respondents=respondents)

    @raises(QuestionnaireError)
    def test_fractional_weight_is_rejected(self):
        respondents = [["respondent", "group", "weight"], ["r1", "g1", 1.5]]
        statistics(respondents=respondents)

    @raises(QuestionnaireError)
    def test_text_weight_is_rejected(self):
        respondents = [["respondent", "group", "weight"], ["r1", "g1", "x"]]
        statistics(respondents=respondents)

    @raises(QuestionnaireError)
    def test_option_for_unknown_question_is_rejected(self):
        options = [
            ["question", "option"],
            ["q404", "yes"],
        ]
        statistics(options=options)

    @raises(QuestionnaireError)
    def test_duplicate_option_is_rejected(self):
        options = [
            ["question", "option"],
            ["q1", "yes"],
            ["q1", "yes"],
        ]
        statistics(options=options)

    @raises(QuestionnaireError)
    def test_child_without_trigger_is_rejected(self):
        questions = [
            ["question", "parent", "trigger"],
            ["q1", "", ""],
            ["q2", "q1", ""],
        ]
        statistics(questions=questions)

    @raises(QuestionnaireError)
    def test_root_with_trigger_is_rejected(self):
        questions = [
            ["question", "parent", "trigger"],
            ["q1", "", "yes"],
        ]
        statistics(questions=questions)

    @raises(QuestionnaireError)
    def test_unknown_column_mapping_is_rejected(self):
        statistics(columns={"unknown": "whatever"})

    @raises(QuestionnaireError)
    def test_missing_required_column_is_rejected(self):
        statistics(questions=[["id", "parent"], ["q1", ""]])

    def test_missing_columns_are_treated_as_blank(self):
        """No group column means a single unnamed group"""
        respondents = [["respondent", "weight"], ["r1", 2]]
        questions = [["question"], ["q1"]]
        options = [["question", "option"], ["q1", "yes"], ["q1", "no"]]
        answers = [
            ["respondent", "question", "option"],
            ["r1", "q1", "yes"],
        ]
        book = pe.questionnaire_statistics(
            questions, options, respondents, answers
        )
        eq_(
            rows(book["option_distribution"]),
            [
                ["", "q1", "yes", 0, 2, 2, 1.0, 1],
                ["", "q1", "no", 0, 0, 2, 0.0, 1],
                ["", "q1", "", 1, 0, 2, 0.0, 1],
            ],
        )

    def test_blank_rows_are_ignored(self):
        respondents = [
            ["respondent", "group", "weight"],
            ["r1", "g1", 1],
            ["", "", ""],
        ]
        answers = [
            ["respondent", "question", "option"],
            ["r1", "q1", "yes"],
            ["", "", ""],
        ]
        questions = [["question", "parent", "trigger"], ["q1", "", ""]]
        options = [["question", "option"], ["q1", "yes"]]
        book = pe.questionnaire_statistics(
            questions, options, respondents, answers
        )
        eq_(len(rows(book["applicable_answers"])), 1)

    def test_result_can_be_saved_like_any_book(self):
        book = statistics()
        content = book.to_dict()
        eq_(
            list(content.keys()),
            ["applicable_answers", "option_distribution", "excluded_answers"],
        )

    def test_three_level_skip_chain(self):
        respondents = [
            ["respondent", "group", "weight"],
            ["r1", "g1", 1],
            ["r2", "g1", 1],
        ]
        answers = [
            ["respondent", "question", "option"],
            ["r1", "q1", "yes"],
            ["r1", "q2", "a"],
            ["r1", "q3", "x"],
            ["r2", "q1", "yes"],
            ["r2", "q2", "b"],
            ["r2", "q3", "x"],
        ]
        book = statistics(respondents=respondents, answers=answers)
        # r2 answered q2 with a non-trigger option, so q3 stays inactive
        # even though r2 has an answer for it
        eq_(
            rows(book["excluded_answers"]),
            [["r2", "g1", 1, "q3", "x", "not applicable"]],
        )
        q3_rows = [
            row for row in rows(book["option_distribution"]) if row[1] == "q3"
        ]
        eq_(
            q3_rows,
            [
                ["g1", "q3", "x", 0, 1, 1, 1.0, 1],
                ["g1", "q3", "y", 0, 0, 1, 0.0, 1],
                ["g1", "q3", "", 1, 0, 1, 0.0, 1],
            ],
        )

    def test_respondent_without_any_answer_is_counted_as_missing(self):
        respondents = [
            ["respondent", "group", "weight"],
            ["r1", "g1", 2],
            ["r2", "g1", 1],
        ]
        answers = [["respondent", "question", "option"]]
        book = statistics(respondents=respondents, answers=answers)
        eq_(
            rows(book["option_distribution"]),
            [
                ["g1", "q1", "yes", 0, 0, 3, 0.0, 2],
                ["g1", "q1", "no", 0, 0, 3, 0.0, 2],
                ["g1", "q1", "", 1, 3, 3, 1.0, 2],
                ["g1", "q2", "a", 0, 0, 0, "", 0],
                ["g1", "q2", "b", 0, 0, 0, "", 0],
                ["g1", "q2", "", 1, 0, 0, "", 0],
                ["g1", "q3", "x", 0, 0, 0, "", 0],
                ["g1", "q3", "y", 0, 0, 0, "", 0],
                ["g1", "q3", "", 1, 0, 0, "", 0],
            ],
        )
        eq_(rows(book["excluded_answers"]), [])

    def test_whitespace_is_ignored_when_matching(self):
        respondents = [
            ["respondent", "group", "weight"],
            [" r1 ", " g1 ", 2],
        ]
        answers = [
            ["respondent", "question", "option"],
            ["r1", "q1", " yes "],
        ]
        options = [
            ["question", "option"],
            ["q1", "yes"],
        ]
        questions = [["question", "parent", "trigger"], ["q1", "", ""]]
        book = pe.questionnaire_statistics(
            questions, options, respondents, answers
        )
        eq_(
            rows(book["applicable_answers"]),
            [[" r1 ", " g1 ", 2, "q1", "yes", 0]],
        )

    def test_numeric_identifiers_are_matched(self):
        respondents = [["respondent", "group", "weight"], [1, "g1", 1]]
        questions = [["question", "parent", "trigger"], [1, "", ""]]
        options = [["question", "option"], [1, "yes"]]
        answers = [["respondent", "question", "option"], ["1", "1", "yes"]]
        book = pe.questionnaire_statistics(
            questions, options, respondents, answers
        )
        eq_(
            rows(book["option_distribution"]),
            [
                ["g1", 1, "yes", 0, 1, 1, 1.0, 1],
                ["g1", 1, "", 1, 0, 1, 0.0, 1],
            ],
        )

    def test_empty_tables_produce_an_empty_book(self):
        book = pe.questionnaire_statistics([], [], [], [])
        eq_(
            book.sheet_names(),
            ["applicable_answers", "option_distribution", "excluded_answers"],
        )
        for sheet_name in book.sheet_names():
            eq_(len(rows(book[sheet_name])), 0)

    def test_header_only_tables_produce_an_empty_book(self):
        book = statistics(
            questions=[["question", "parent", "trigger"]],
            options=[["question", "option"]],
            respondents=[["respondent", "group", "weight"]],
            answers=[["respondent", "question", "option"]],
        )
        eq_(rows(book["applicable_answers"]), [])
        eq_(rows(book["option_distribution"]), [])
        eq_(rows(book["excluded_answers"]), [])
