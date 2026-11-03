import 'dart:convert';

import '../../sync/projection_contract.dart';

/// Validates the Django Discovery wire without deriving domain truth.
///
/// The payload is kept whole. Presentation may humanize these facts later,
/// but reception never replaces UNKNOWN, authorization or provenance.
final class DiscoveryWire {
  const DiscoveryWire._({required this.data, required this.meta});

  static const projection = 'discovery.items';
  static const snapshotMetaKey = '_discovery_envelope_meta';

  final Map<String, dynamic> data;
  final Map<String, dynamic> meta;

  static DiscoveryWire receive(
    Map<String, dynamic> response, {
    required String scope,
  }) {
    final envelope = ProjectionEnvelope.parse(
      response,
      expectedProjection: projection,
      expectedScope: scope,
    );
    final data = Map<String, dynamic>.from(envelope.data);
    validateData(data, currentWire: true);
    if (scope == 'public') {
      if (data['surface'] != 'discover_public' ||
          data['actor'] != null ||
          data['viewer'] != null) {
        throw const FormatException('Private context in public Discovery');
      }
    } else if (scope == 'personal') {
      final actor = _map(data['actor']);
      final viewer = _map(data['viewer']);
      if (data['surface'] != 'discover_me' ||
          actor?['type'] != 'profile' ||
          viewer?['type'] != 'profile' ||
          !_nonEmpty(actor?['id']) ||
          actor?['id'] != viewer?['id']) {
        throw const FormatException('Invalid personal Discovery context');
      }
    } else {
      throw const FormatException('Unsupported Discovery scope');
    }

    return DiscoveryWire._(
      data: Map.unmodifiable(data),
      meta: Map.unmodifiable(envelope.meta),
    );
  }

  static Map<String, dynamic> receiveItem(
    Map<String, dynamic> response, {
    required String scope,
  }) {
    final envelope = ProjectionEnvelope.parse(
      response,
      expectedProjection: 'discovery.item',
      expectedScope: scope,
    );
    final item = _map(envelope.data['item']);
    if (item == null) {
      throw const FormatException('Missing Discovery detail');
    }
    validateData({
      'results': [item],
    });
    return Map.unmodifiable(item);
  }

  /// Existing snapshots from before B1 may omit new optional metadata.
  /// A malformed identity or a malformed exposed fact remains an error.
  static void validateData(
    Map<String, dynamic> data, {
    bool currentWire = false,
  }) {
    final results = data['results'] ?? data['items'];
    if (results is! List) {
      throw const FormatException('Missing Discovery results');
    }
    if (data['results'] != null && data['items'] != null) {
      final alias = data['items'];
      if (alias is! List || alias.length != results.length) {
        throw const FormatException('Inconsistent Discovery results alias');
      }
      for (var i = 0; i < results.length; i++) {
        final a = _map(results[i]);
        final b = _map(alias[i]);
        if (a == null ||
            b == null ||
            _map(a['identity'])?['candidate_key'] !=
                _map(b['identity'])?['candidate_key'] ||
            jsonEncode(a) != jsonEncode(b)) {
          throw const FormatException('Inconsistent Discovery item identity');
        }
      }
    }
    for (final raw in results) {
      final item = _map(raw);
      final identity = _map(item?['identity']);
      final resource = _map(identity?['resource']);
      final representation = _map(item?['representation']);
      if (item == null ||
          identity == null ||
          !_nonEmpty(identity['family']) ||
          !_nonEmpty(identity['candidate_key']) ||
          !_nonEmpty(resource?['kind']) ||
          !_nonEmpty(resource?['id']) ||
          !_nonEmpty(representation?['title'])) {
        throw const FormatException('Invalid Discovery candidate identity');
      }
      for (final key in [
        'variants',
        'relations',
        'temporal_facts',
        'spatial_facts',
        'media_bindings',
        'assessment',
        'facts',
        'presentation_facts',
      ]) {
        final value = item[key];
        if (value != null &&
            (value is! List || value.any((element) => element is! Map))) {
          throw FormatException('Invalid Discovery fact collection: $key');
        }
      }
      for (final key in [
        'owner',
        'provenance',
        'personal_relation',
        'saved',
        'watch',
        'price',
        'place',
        'timing',
        'availability',
        'engagement',
        'participant_presentation',
        'knowledge',
        'freshness',
        'detail',
      ]) {
        if (item[key] != null && item[key] is! Map) {
          throw FormatException('Invalid Discovery object: $key');
        }
      }
      if (item['capabilities'] != null &&
          (item['capabilities'] is! List ||
              (item['capabilities'] as List).any(
                (value) => value is! String,
              ))) {
        throw const FormatException('Invalid Discovery capabilities');
      }
      if (item['links'] != null &&
          (item['links'] is! Map ||
              (item['links'] as Map).values.any(
                (value) => value != null && value is! String,
              ))) {
        throw const FormatException('Invalid Discovery links');
      }
      for (final key in ['occurrence', 'revision']) {
        final reference = identity[key];
        if (reference != null &&
            (_map(reference) == null ||
                !_nonEmpty(_map(reference)?['kind']) ||
                !_nonEmpty(_map(reference)?['id']))) {
          throw FormatException('Invalid Discovery reference: $key');
        }
      }
    }
    if (!currentWire) return;
    if (data['count'] is! int ||
        data['page'] is! int ||
        data['page_size'] is! int ||
        (data['count'] as int) < 0 ||
        (data['page'] as int) < 1 ||
        (data['page_size'] as int) < 1 ||
        data['has_next'] is! bool) {
      throw const FormatException('Invalid Discovery pagination');
    }
    for (final key in [
      'exploration',
      'freshness',
      'selection',
      'terminal',
      'continuation',
    ]) {
      if (data[key] is! Map) {
        throw FormatException('Missing Discovery context: $key');
      }
    }
    if (data['capabilities'] != null &&
        (data['capabilities'] is! List ||
            (data['capabilities'] as List).any((value) => value is! String))) {
      throw const FormatException('Invalid Discovery collection capabilities');
    }
    if (data['handoffs'] != null &&
        (data['handoffs'] is! List ||
            (data['handoffs'] as List).any((value) => value is! Map))) {
      throw const FormatException('Invalid Discovery collection handoffs');
    }
    final continuation = _map(data['continuation'])!;
    if (continuation['state'] != 'more' && continuation['state'] != 'end') {
      throw const FormatException('Invalid Discovery continuation state');
    }
    final token = continuation['token'];
    if (data['has_next'] == true &&
        (continuation['state'] != 'more' || !_nonEmpty(token))) {
      throw const FormatException('Missing opaque Discovery continuation');
    }
    if (data['has_next'] == false &&
        (continuation['state'] != 'end' || token != null)) {
      throw const FormatException('Invalid final Discovery continuation');
    }
    final selection = _map(data['selection'])!;
    final terminal = _map(data['terminal'])!;
    if (!{'ready', 'empty'}.contains(selection['state']) ||
        !{'ok', 'empty', 'end_of_field'}.contains(terminal['state'])) {
      throw const FormatException('Invalid Discovery selection or terminal');
    }
  }

  Map<String, dynamic> get snapshotPayload => {...data, snapshotMetaKey: meta};

  static Map<String, dynamic>? _map(Object? value) =>
      value is Map ? Map<String, dynamic>.from(value) : null;

  static bool _nonEmpty(Object? value) =>
      value is String && value.trim().isNotEmpty;
}
