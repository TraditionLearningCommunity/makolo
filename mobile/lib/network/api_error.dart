import 'dart:convert';

class MakoloApiError implements Exception {
  const MakoloApiError({
    required this.statusCode,
    required this.code,
    required this.message,
    this.fields = const {},
  });

  final int statusCode;
  final String code;
  final String message;
  final Map<String, dynamic> fields;

  static MakoloApiError fromResponse(int statusCode, String body) {
    try {
      final decoded = jsonDecode(body);
      if (decoded is Map<String, dynamic>) {
        final nested = decoded['error'];
        if (nested is Map<String, dynamic>) {
          return MakoloApiError(
            statusCode: statusCode,
            code: nested['code']?.toString() ?? 'api_error',
            message:
                nested['message']?.toString() ?? 'Une erreur est survenue.',
            fields: nested['fields'] is Map<String, dynamic>
                ? nested['fields'] as Map<String, dynamic>
                : const {},
          );
        }
        final detail = decoded['detail'];
        if (detail != null) {
          return MakoloApiError(
            statusCode: statusCode,
            code: statusCode == 401 ? 'authentication_required' : 'api_error',
            message: detail.toString(),
          );
        }
        return MakoloApiError(
          statusCode: statusCode,
          code: 'api_error',
          message: decoded.values.map((value) => value.toString()).join(' · '),
          fields: decoded,
        );
      }
    } on Object {
      // Fall through to a transport-safe error without exposing the body.
    }
    return MakoloApiError(
      statusCode: statusCode,
      code: 'http_$statusCode',
      message: 'Le serveur n’a pas pu traiter cette demande.',
    );
  }

  @override
  String toString() => 'MakoloApiError($code, $statusCode)';
}
