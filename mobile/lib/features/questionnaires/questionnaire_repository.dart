import 'package:drift/drift.dart';

import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../network/makolo_api_client.dart';
import '../../sync/freshness.dart';
import '../../sync/sync_engine.dart';
import '../../sync/sync_source.dart';

enum QuestionnaireQuestionType {
  shortText('short_text'),
  longText('long_text'),
  boolean('boolean'),
  singleChoice('single_choice'),
  multipleChoice('multiple_choice'),
  number('number'),
  date('date');

  const QuestionnaireQuestionType(this.wireValue);
  final String wireValue;

  static QuestionnaireQuestionType parse(Object? value) {
    final wire = value?.toString();
    return values.firstWhere(
      (type) => type.wireValue == wire,
      orElse: () => throw FormatException(
        'Unsupported questionnaire question type: ' + (wire ?? 'null'),
      ),
    );
  }
}

class QuestionnaireOwnerLinks {
  const QuestionnaireOwnerLinks({
    required this.detail,
    this.save,
    this.submit,
  });

  final String detail;
  final String? save;
  final String? submit;

  bool get canSubmit => save != null && submit != null;
}

class QuestionnaireQuestion {
  const QuestionnaireQuestion({
    required this.key,
    required this.label,
    required this.type,
    required this.position,
    required this.required,
    required this.choices,
    this.helpText,
    this.minLength,
    this.maxLength,
    this.minValue,
    this.maxValue,
  });

  final String key;
  final String label;
  final QuestionnaireQuestionType type;
  final int position;
  final bool required;
  final List<String> choices;
  final String? helpText;
  final int? minLength;
  final int? maxLength;
  final num? minValue;
  final num? maxValue;
}

class QuestionnaireRequestDetail {
  const QuestionnaireRequestDetail({
    required this.id,
    required this.required,
    required this.status,
    required this.formVersionId,
    required this.formKey,
    required this.version,
    required this.title,
    required this.questions,
    required this.answers,
    this.journeyId,
    this.opensAt,
    this.dueAt,
    this.description,
    this.responseId,
    this.responseStatus,
    this.submittedAt,
  });

  final String id;
  final String? journeyId;
  final bool required;
  final String status;
  final DateTime? opensAt;
  final DateTime? dueAt;
  final String formVersionId;
  final String formKey;
  final int version;
  final String title;
  final String? description;
  final List<QuestionnaireQuestion> questions;
  final String? responseId;
  final String? responseStatus;
  final DateTime? submittedAt;
  final Map<String, dynamic> answers;

  bool get isSubmitted =>
      responseStatus == 'submitted' || status == 'completed';

  factory QuestionnaireRequestDetail.fromPayload(Map<String, dynamic> payload) {
    String requiredString(Object? value, String field) {
      final text = value?.toString().trim();
      if (text == null || text.isEmpty) {
        throw FormatException('Missing questionnaire field: ' + field);
      }
      return text;
    }

    Map<String, dynamic> map(Object? value, String field) {
      if (value is Map<String, dynamic>) return value;
      if (value is Map) {
        return value.map((key, item) => MapEntry(key.toString(), item));
      }
      throw FormatException('Expected questionnaire object: ' + field);
    }

    final formVersion = map(payload['form_version'], 'form_version');
    final rawQuestions = formVersion['questions'];
    if (rawQuestions is! List) {
      throw const FormatException('Expected questionnaire questions list.');
    }

    final questions = rawQuestions.map((raw) {
      final question = map(raw, 'question');
      final rawChoices = question['choices'];
      final choices = rawChoices is List
          ? rawChoices.map((item) => item.toString()).toList(growable: false)
          : const <String>[];
      return QuestionnaireQuestion(
        key: requiredString(question['key'], 'question.key'),
        label: requiredString(question['label'], 'question.label'),
        type: QuestionnaireQuestionType.parse(question['type']),
        position: question['position'] is int
            ? question['position'] as int
            : int.tryParse(question['position']?.toString() ?? '') ?? 0,
        required: question['required'] == true,
        helpText: _optionalString(question['help_text']),
        minLength: _optionalInt(question['min_length']),
        maxLength: _optionalInt(question['max_length']),
        minValue: _optionalNum(question['min_value']),
        maxValue: _optionalNum(question['max_value']),
        choices: choices,
      );
    }).toList(growable: false)
      ..sort((a, b) => a.position.compareTo(b.position));

    final rawResponse = payload['response'];
    final response = rawResponse == null
        ? null
        : map(rawResponse, 'response');
    final rawAnswers = response?['answers'];
    final answers = rawAnswers is Map
        ? rawAnswers.map((key, value) => MapEntry(key.toString(), value))
        : <String, dynamic>{};

    return QuestionnaireRequestDetail(
      id: requiredString(payload['id'], 'id'),
      journeyId: _optionalString(payload['journey_id']),
      required: payload['required'] == true,
      status: requiredString(payload['status'], 'status'),
      opensAt: _optionalDateTime(payload['opens_at']),
      dueAt: _optionalDateTime(payload['due_at']),
      formVersionId: requiredString(formVersion['id'], 'form_version.id'),
      formKey: requiredString(formVersion['form_key'], 'form_version.form_key'),
      version: formVersion['version'] is int
          ? formVersion['version'] as int
          : int.tryParse(formVersion['version']?.toString() ?? '') ?? 0,
      title: requiredString(formVersion['title'], 'form_version.title'),
      description: _optionalString(formVersion['description']),
      questions: List.unmodifiable(questions),
      responseId: _optionalString(response?['id']),
      responseStatus: _optionalString(response?['status']),
      submittedAt: _optionalDateTime(response?['submitted_at']),
      answers: Map.unmodifiable(answers),
    );
  }

  static String? _optionalString(Object? value) {
    final text = value?.toString().trim();
    return text == null || text.isEmpty ? null : text;
  }

  static int? _optionalInt(Object? value) {
    if (value is int) return value;
    return int.tryParse(value?.toString() ?? '');
  }

  static num? _optionalNum(Object? value) {
    if (value is num) return value;
    return num.tryParse(value?.toString() ?? '');
  }

  static DateTime? _optionalDateTime(Object? value) {
    final text = _optionalString(value);
    return text == null ? null : DateTime.tryParse(text);
  }
}

class QuestionnaireRepository {
  QuestionnaireRepository({
    required this.database,
    required this.store,
    required this.profileId,
    this.sync,
  });

  static const projectionKind = 'questionnaire.form.request.detail';
  static const freshnessPolicy = FreshnessPolicy(
    id: 'questionnaire-request-contextual',
    refreshRecommendedAfter: Duration(hours: 1),
    revalidateBeforeAction: true,
  );

  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;
  final SyncEngine? sync;

  SyncSourceDefinition sourceFor({
    required String requestId,
    required String detailPath,
  }) {
    if (detailPath.trim().isEmpty) {
      throw ArgumentError.value(detailPath, 'detailPath', 'Owner link required');
    }
    return SyncSourceDefinition(
      sourceKey: 'questionnaire-request:' + requestId,
      owner: 'Questionnaires',
      path: _relativeApiPath(detailPath),
      projectionKind: projectionKind,
      resourceKey: requestId,
      category: SyncSourceCategory.keyedDetail,
      freshnessPolicy: freshnessPolicy,
      parser: (response) {
        final payload = response.jsonObject();
        final parsed = QuestionnaireRequestDetail.fromPayload(payload);
        if (parsed.id != requestId) {
          throw FormatException(
            'Expected questionnaire request ' +
                requestId +
                ', got ' +
                parsed.id,
          );
        }
        return AcquiredProjection(schemaVersion: 1, payload: payload);
      },
      applier: applyProjectionSnapshot,
    );
  }

  Stream<StoredProjection?> watchDetail(String requestId) {
    return store.watchProjection(projectionKind, resourceKey: requestId);
  }

  Future<StoredProjection?> readDetail(String requestId) {
    return store.readProjection(projectionKind, resourceKey: requestId);
  }

  Future<QuestionnaireRequestDetail?> readParsed(String requestId) async {
    final projection = await readDetail(requestId);
    if (projection == null) return null;
    return QuestionnaireRequestDetail.fromPayload(projection.payload);
  }

  Future<void> refresh({
    required String requestId,
    required String detailPath,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Questionnaire owner is not configured.');
    }
    await engine.refreshSource(
      sourceFor(requestId: requestId, detailPath: detailPath),
    );
  }

  Future<void> applyOwnerResponse({
    required String requestId,
    required ApiResponse response,
  }) async {
    final payload = response.jsonObject();
    final parsed = QuestionnaireRequestDetail.fromPayload(payload);
    if (parsed.id != requestId) {
      throw FormatException(
        'Expected questionnaire request ' +
            requestId +
            ', got ' +
            parsed.id,
      );
    }
    await store.putProjection(
      kind: projectionKind,
      resourceKey: requestId,
      schemaVersion: 1,
      payload: payload,
      lastVerifiedOnlineAt: DateTime.now().toUtc(),
      freshnessPolicyId: freshnessPolicy.id,
    );
  }

  static String _relativeApiPath(String value) {
    final trimmed = value.trim();
    if (trimmed.startsWith('/')) return trimmed.substring(1);
    return trimmed;
  }
}
