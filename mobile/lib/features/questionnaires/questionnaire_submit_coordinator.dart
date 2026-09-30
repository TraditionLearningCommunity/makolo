import 'dart:convert';

import '../../auth/token_store.dart';
import '../../features/journey/journey_repository.dart';
import '../../network/api_error.dart';
import '../../network/makolo_api_client.dart';
import '../../repositories/draft_repository.dart';
import '../../sync/outbox/outbox_processor.dart';
import '../../sync/outbox/outbox_repository.dart';
import 'questionnaire_repository.dart';

class QuestionnaireSubmitCoordinator {
  QuestionnaireSubmitCoordinator({
    required this.api,
    required this.tokens,
    required this.outbox,
    required this.drafts,
    required this.questionnaires,
    required this.journeys,
  });

  static const operationKind = 'questionnaire.form.submit';
  static const owner = 'Questionnaires';
  static const resourceKind = 'form_request';

  final MakoloApiClient api;
  final TokenStore tokens;
  final OutboxRepository outbox;
  final DraftRepository drafts;
  final QuestionnaireRepository questionnaires;
  final JourneyRepository journeys;

  OutboxHandler get handler => _execute;
  OutboxReconciler get reconciler => _reconcile;

  Future<bool> enqueue({
    required String requestId,
    required String journeyId,
    required Map<String, dynamic> answers,
    required QuestionnaireOwnerLinks links,
  }) async {
    if (!links.canSubmit) {
      throw StateError('Questionnaire owner did not grant complete_form.');
    }
    final existing = await outbox.activeForResource(
      operationKind: operationKind,
      resourceId: requestId,
    );
    if (existing != null) return false;

    final deviceId = await tokens.deviceInstanceId();
    final stamp = DateTime.now().toUtc().microsecondsSinceEpoch.toString();
    final intentId = 'questionnaire-submit:' + requestId + ':' + stamp;
    final operationId = deviceId + ':' + intentId;
    final draftId = 'questionnaire:' + requestId;

    await drafts.saveLocal(
      draftId: draftId,
      owner: owner,
      resourceKind: resourceKind,
      resourceId: requestId,
      payload: <String, dynamic>{
        'answers': answers,
        'base_observed_at': DateTime.now().toUtc().toIso8601String(),
      },
    );
    await outbox.enqueue(
      operationId: operationId,
      deviceInstanceId: deviceId,
      operationKind: operationKind,
      owner: owner,
      resourceKind: resourceKind,
      resourceId: requestId,
      payload: <String, dynamic>{
        'request_id': requestId,
        'journey_id': journeyId,
        'answers': answers,
        'links': <String, dynamic>{
          'detail': links.detail,
          'save': links.save,
          'submit': links.submit,
        },
      },
      intentId: intentId,
      replayPolicy: ReplayPolicy.refetchBeforeRetry,
    );
    return true;
  }

  Future<OutboxResolution> _execute(OutboxOperation operation) async {
    final payload = _payload(operation);
    final requestId = _requiredString(payload, 'request_id');
    final journeyId = _requiredString(payload, 'journey_id');
    final answers = _answers(payload['answers']);
    final links = _links(payload);

    try {
      final saved = await api.post(
        _relative(links.save!),
        body: <String, dynamic>{'answers': answers},
      );
      await questionnaires.applyOwnerResponse(
        requestId: requestId,
        response: saved,
      );

      final submitted = await api.post(_relative(links.submit!));
      await questionnaires.applyOwnerResponse(
        requestId: requestId,
        response: submitted,
      );
      final parsed = QuestionnaireRequestDetail.fromPayload(
        submitted.jsonObject(),
      );
      if (!parsed.isSubmitted) {
        return OutboxResolution.awaitingConfirmation;
      }
      await _finalizeConfirmed(
        requestId: requestId,
        journeyId: journeyId,
      );
      return OutboxResolution.confirmed;
    } on MakoloApiError catch (error) {
      if (error.statusCode == 400) {
        await _recordValidationErrors(
          requestId: requestId,
          answers: answers,
          error: error,
        );
        return OutboxResolution.conflict;
      }
      if (error.statusCode == 403) {
        return OutboxResolution.conflict;
      }
      if (error.statusCode == 404) {
        return OutboxResolution.failed;
      }
      rethrow;
    }
  }

  Future<OutboxResolution> _reconcile(OutboxOperation operation) async {
    final payload = _payload(operation);
    final requestId = _requiredString(payload, 'request_id');
    final journeyId = _requiredString(payload, 'journey_id');
    final links = _links(payload);

    try {
      final response = await api.get(_relative(links.detail));
      await questionnaires.applyOwnerResponse(
        requestId: requestId,
        response: response,
      );
      final parsed = QuestionnaireRequestDetail.fromPayload(
        response.jsonObject(),
      );
      if (parsed.isSubmitted) {
        await _finalizeConfirmed(
          requestId: requestId,
          journeyId: journeyId,
        );
        return OutboxResolution.confirmed;
      }
      if (parsed.status == 'cancelled') {
        return OutboxResolution.conflict;
      }
      if (parsed.status == 'requested' &&
          (parsed.responseStatus == null ||
              parsed.responseStatus == 'draft' ||
              parsed.responseStatus == 'reopened')) {
        return OutboxResolution.retryable;
      }
      return OutboxResolution.conflict;
    } on MakoloApiError catch (error) {
      if (error.statusCode == 403) return OutboxResolution.conflict;
      if (error.statusCode == 404) return OutboxResolution.failed;
      return OutboxResolution.awaitingConfirmation;
    } on Object {
      return OutboxResolution.awaitingConfirmation;
    }
  }

  Future<void> _finalizeConfirmed({
    required String requestId,
    required String journeyId,
  }) async {
    await drafts.delete(
      owner: owner,
      resourceKind: resourceKind,
      resourceId: requestId,
    );
    await journeys.invalidateDetail(journeyId);
    try {
      await journeys.refreshDetail(journeyId);
    } on Object {
      // The confirmed owner mutation remains true. Journey stays invalidated
      // until normal sync can acquire the next server-owned projection.
    }
  }

  Future<void> _recordValidationErrors({
    required String requestId,
    required Map<String, dynamic> answers,
    required MakoloApiError error,
  }) {
    final raw = error.fields['errors'];
    final errors = raw is Map
        ? raw.map((key, value) => MapEntry(key.toString(), value))
        : <String, dynamic>{'_form': error.message};
    return drafts.saveLocal(
      draftId: 'questionnaire:' + requestId,
      owner: owner,
      resourceKind: resourceKind,
      resourceId: requestId,
      payload: <String, dynamic>{
        'answers': answers,
        'server_errors': errors,
        'base_observed_at': DateTime.now().toUtc().toIso8601String(),
      },
    );
  }

  Map<String, dynamic> _payload(OutboxOperation operation) {
    final value = jsonDecode(operation.payloadJson);
    if (value is! Map) {
      throw const FormatException('Questionnaire outbox payload must be an object.');
    }
    return value.map((key, item) => MapEntry(key.toString(), item));
  }

  QuestionnaireOwnerLinks _links(Map<String, dynamic> payload) {
    final raw = payload['links'];
    if (raw is! Map) {
      throw const FormatException('Questionnaire owner links are required.');
    }
    final values = raw.map((key, value) => MapEntry(key.toString(), value));
    final detail = _requiredString(values, 'detail');
    final save = values['save']?.toString().trim();
    final submit = values['submit']?.toString().trim();
    if (save == null || save.isEmpty || submit == null || submit.isEmpty) {
      throw const FormatException('Questionnaire save/submit owner links are required.');
    }
    return QuestionnaireOwnerLinks(
      detail: detail,
      save: save,
      submit: submit,
    );
  }

  Map<String, dynamic> _answers(Object? value) {
    if (value is! Map) {
      throw const FormatException('Questionnaire answers must be an object.');
    }
    return value.map((key, item) => MapEntry(key.toString(), item));
  }

  String _requiredString(Map<String, dynamic> value, String key) {
    final text = value[key]?.toString().trim();
    if (text == null || text.isEmpty) {
      throw FormatException('Missing questionnaire outbox field: ' + key);
    }
    return text;
  }

  String _relative(String value) {
    final trimmed = value.trim();
    return trimmed.startsWith('/') ? trimmed.substring(1) : trimmed;
  }
}
