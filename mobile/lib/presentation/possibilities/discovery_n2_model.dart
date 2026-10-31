import '../../features/discovery/discovery_selector.dart';

/// Read-only N2 interpretation of the admitted owner's projection.
/// No eligibility, price, ranking, alternative or authorization is inferred.
class DiscoveryN2Assessment {
  const DiscoveryN2Assessment(this.state, this.label);
  final String state;
  final String label;
}

class DiscoveryN2Variant {
  const DiscoveryN2Variant({
    required this.id,
    required this.start,
    required this.end,
    required this.places,
  });

  final String id;
  final String? start;
  final String? end;
  final List<String> places;
}

class DiscoveryN2ComparisonRow {
  const DiscoveryN2ComparisonRow(this.label, this.values);
  final String label;
  final List<String> values;
}

class DiscoveryN2Depth {
  DiscoveryN2Depth(DiscoveryItemPresentation item)
      : assessments = _assessments(item),
        variants = _variants(item),
        relations = _relations(item),
        provenance = _provenance(item),
        freshness = _freshness(item);

  final List<DiscoveryN2Assessment> assessments;
  final List<DiscoveryN2Variant> variants;
  final List<String> relations;
  final List<String> provenance;
  final String? freshness;

  /// Variant comparison is allowed only *inside* the same owner's admitted
  /// possibility, with at least two distinct Occurrence identities.
  /// There is no cross-vertical universal comparison, missing-value imputation,
  /// local winner, or price/availability copied from the parent Activity.
  List<DiscoveryN2ComparisonRow> get comparisonRows {
    if (variants.length < 2) return const [];
    final rows = <DiscoveryN2ComparisonRow>[];
    void consider(String label, String? Function(DiscoveryN2Variant) read) {
      final values = variants.map(read).toList();
      if (values.any((v) => v == null || v.trim().isEmpty)) return;
      final actual = values.cast<String>();
      if (actual.toSet().length < 2) return;
      rows.add(DiscoveryN2ComparisonRow(label, List.unmodifiable(actual)));
    }

    consider('Début', (v) => v.start);
    consider('Fin', (v) => v.end);
    consider('Lieu', (v) => v.places.isEmpty ? null : v.places.join(' · '));
    return List.unmodifiable(rows);
  }

  static List<DiscoveryN2Assessment> _assessments(DiscoveryItemPresentation item) {
    const states = {'favorable', 'limiting', 'unknown'};
    final seen = <String>{};
    final result = <DiscoveryN2Assessment>[];
    for (final raw in item.assessment) {
      final state = (raw['state'] ?? '').toString();
      final label = (raw['label'] ?? '').toString().trim();
      if (!states.contains(state) || label.isEmpty ||
          !seen.add('$state:$label')) continue;
      result.add(DiscoveryN2Assessment(state, label));
    }
    return List.unmodifiable(result);
  }

  static String? _text(Object? value) {
    if (value is! String) return null;
    final text = value.trim();
    if (text.isEmpty || const {'unknown', 'null', 'none', 'n/a'}.contains(
      text.toLowerCase(),
    )) return null;
    return text;
  }

  static String? _time(Map data, String direct, String fallbackDate, String fallbackTime) {
    final exact = _text(data[direct]);
    if (exact != null) {
      return exact.replaceFirst('T', ' ');
    }
    final day = _text(data[fallbackDate]);
    final clock = _text(data[fallbackTime]);
    if (day == null) return null;
    final zone = _text(data['timezone']);
    return [day, if (clock != null) clock, if (zone != null) zone].join(' · ');
  }

  static List<DiscoveryN2Variant> _variants(DiscoveryItemPresentation item) {
    if (item.family != 'activity') return const [];
    // An Occurrence may appear under several spatial roles; its stable key
    // comes only from a server-published Occurrence reference.
    final byOccurrence = <String, List<String>>{};
    for (final fact in item.spatialFacts) {
      final occurrence = fact['occurrence'];
      final place = fact['place'];
      if (occurrence is! Map || place is! Map ||
          occurrence['kind'] != 'occurrence') continue;
      final id = _text(occurrence['id']);
      if (id == null) continue;
      final name = _text(place['name']);
      final locality = _text(place['locality']);
      final label = name == null ? locality :
          (locality != null && name.toLowerCase() != locality.toLowerCase()
              ? '$name, $locality' : name);
      if (label == null) continue;
      final places = byOccurrence.putIfAbsent(id, () => []);
      if (!places.contains(label)) places.add(label);
    }

    final seen = <String>{};
    final result = <DiscoveryN2Variant>[];
    for (final raw in item.variants) {
      final occurrence = raw['occurrence'];
      if (occurrence is! Map || occurrence['kind'] != 'occurrence') continue;
      final id = _text(occurrence['id']);
      if (id == null || !seen.add(id)) continue;
      final timing = raw['timing'];
      final schedule = timing is Map ? timing : const {};
      result.add(DiscoveryN2Variant(
        id: id,
        start: _time(schedule, 'start_at', 'start_date', 'start_time'),
        end: _time(schedule, 'end_at', 'end_date', 'end_time'),
        places: List.unmodifiable(byOccurrence[id] ?? const <String>[]),
      ));
    }
    return List.unmodifiable(result);
  }

  static List<String> _relations(DiscoveryItemPresentation item) {
    final result = <String>[];
    for (final relation in item.relations) {
      // Neither an unknown relationship code nor a coincidentally similar
      // title can justify an alternative/comparison.
      final label = _text(relation['label']);
      if (label != null && !result.contains(label)) result.add(label);
    }
    return List.unmodifiable(result);
  }

  static List<String> _provenance(DiscoveryItemPresentation item) {
    final result = <String>[];
    final resources = item.provenance?['resources'];
    if (resources is! List) return const [];
    for (final resource in resources) {
      if (resource is! Map) continue;
      final kind = _text(resource['kind']);
      final id = _text(resource['id']);
      if (kind == null || id == null) continue;
      final text = '$kind · $id';
      if (!result.contains(text)) result.add(text);
    }
    return List.unmodifiable(result);
  }

  static String? _freshness(DiscoveryItemPresentation item) {
    final facts = item.freshness;
    if (facts == null) return null;
    // Only a source-provided freshness label is usable. A client clock does
    // not silently upgrade server truth.
    return _text(facts['label']);
  }
}
