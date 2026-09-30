import 'dart:convert';

import 'destination.dart';

class StructuredDestinationCodec {
  const StructuredDestinationCodec();

  static const int schemaVersion = 1;

  StructuredDestination? fromNavigation(Object? value) {
    if (value is! Map) return null;
    if (value['schema_version'] != schemaVersion) return null;

    final resource = value['resource'];
    if (resource is! Map) return null;

    final kind = resource['kind']?.toString().trim();
    final id = resource['id']?.toString().trim();
    if (kind == null || kind.isEmpty || id == null || id.isEmpty) {
      return null;
    }

    String? link;
    final links = value['links'];
    if (links is Map) {
      final candidate = links['api']?.toString().trim();
      if (candidate != null && candidate.isNotEmpty) link = candidate;
    }

    return StructuredDestination(kind: kind, id: id, link: link);
  }

  StructuredDestination? fromJson(String encoded) {
    try {
      return fromNavigation(jsonDecode(encoded));
    } on FormatException {
      return null;
    }
  }

  Map<String, Object> toNavigation(StructuredDestination destination) {
    return <String, Object>{
      'schema_version': schemaVersion,
      'resource': <String, String>{
        'kind': destination.kind,
        'id': destination.id,
      },
      if (destination.link != null && destination.link!.isNotEmpty)
        'links': <String, String>{'api': destination.link!},
    };
  }

  String toJson(StructuredDestination destination) =>
      jsonEncode(toNavigation(destination));
}
