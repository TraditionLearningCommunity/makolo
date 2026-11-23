"""Reusable owner-scoped form presentation for pages and inline Conversations.

Answers, media and submission remain owned by questionnaires; no separate
Conversation response model or validation is introduced here.
"""
from .media_services import media_sections


def questionnaire_response_presentation(form_request):
    response = getattr(form_request, "response", None)
    answers = (
        {answer.question_id: answer.value for answer in response.answers.all()}
        if response else {}
    )
    root, questions, choices = media_sections(form_request.form_version)
    rows = [
        {
            "question": question,
            "value": answers.get(question.pk),
            "media": questions.get(question.pk, []),
            "choices": [
                {"label": label, "media": choices.get((question.pk, index), [])}
                for index, label in enumerate(question.choices)
            ],
        }
        for question in form_request.form_version.questions.all()
    ]
    return {
        "form_request": form_request,
        "form_response": response,
        "form_media": root,
        "question_rows": rows,
    }
