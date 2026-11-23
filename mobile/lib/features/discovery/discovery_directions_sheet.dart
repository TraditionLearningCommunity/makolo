import 'package:flutter/material.dart';

import '../../platform/maps/external_directions.dart';
import 'discovery_selector.dart';

class DiscoveryDirectionsDestination {
  const DiscoveryDirectionsDestination({
    required this.latitude,
    required this.longitude,
    required this.label,
  });

  final double latitude;
  final double longitude;
  final String label;
}

/// The owner-projected spatial facts, not titles or search text, determine
/// the destination. For a Journey with departure/arrival the person chooses
/// the intended stop instead of silently routing to an arbitrary one.
List<DiscoveryDirectionsDestination> discoveryDirectionsDestinations(
  DiscoveryItemPresentation item,
) {
  final result = <DiscoveryDirectionsDestination>[];
  final seen = <String>{};
  double? coordinate(Object? value) {
    if (value is num) return value.toDouble();
    if (value is String) return double.tryParse(value);
    return null;
  }

  for (final fact in item.spatialFacts) {
    final place = fact['place'];
    if (place is! Map) continue;
    final latitude = coordinate(place['latitude']);
    final longitude = coordinate(place['longitude']);
    if (latitude == null ||
        longitude == null ||
        !ExternalDirections.valid(latitude, longitude)) {
      continue;
    }
    final key = '$latitude:$longitude';
    if (!seen.add(key)) continue;
    final name = (place['name'] ?? place['locality'] ?? item.place ?? 'Lieu')
        .toString();
    final role = fact['role']?.toString();
    final prefix = switch (role) {
      'departure' => 'Départ',
      'arrival' => 'Arrivée',
      'stopover' => 'Escale',
      'boarding' => 'Embarquement',
      'dropoff' => 'Débarquement',
      _ => '',
    };
    result.add(
      DiscoveryDirectionsDestination(
        latitude: latitude,
        longitude: longitude,
        label: prefix.isEmpty ? name : '$prefix · $name',
      ),
    );
  }
  if (result.isEmpty &&
      item.latitude != null &&
      item.longitude != null &&
      ExternalDirections.valid(item.latitude!, item.longitude!)) {
    result.add(
      DiscoveryDirectionsDestination(
        latitude: item.latitude!,
        longitude: item.longitude!,
        label: item.place ?? 'Lieu de l’activité',
      ),
    );
  }
  return List.unmodifiable(result);
}

Future<void> showDiscoveryItemDirections(
  BuildContext context,
  DiscoveryItemPresentation item,
) async {
  final destinations = discoveryDirectionsDestinations(item);
  if (destinations.isEmpty) return;
  var target = destinations.first;
  if (destinations.length > 1) {
    final chosen = await showModalBottomSheet<DiscoveryDirectionsDestination>(
      context: context,
      useSafeArea: true,
      showDragHandle: true,
      builder: (sheetContext) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: Text(
                'Quel lieu rejoindre ?',
                style: Theme.of(sheetContext).textTheme.titleMedium,
              ),
            ),
            for (final destination in destinations)
              ListTile(
                leading: const Icon(Icons.place_outlined),
                title: Text(destination.label),
                onTap: () => Navigator.of(sheetContext).pop(destination),
              ),
          ],
        ),
      ),
    );
    if (chosen == null || !context.mounted) return;
    target = chosen;
  }
  if (!context.mounted) return;
  await showDiscoveryDirections(
    context,
    latitude: target.latitude,
    longitude: target.longitude,
  );
}

/// Direct handoff to Google Maps through Android's external URL resolver.
/// The same official HTTPS URL falls back to a browser when Maps is absent.
Future<void> showDiscoveryDirections(
  BuildContext context, {
  required double latitude,
  required double longitude,
}) async {
  if (!ExternalDirections.valid(latitude, longitude)) return;
  final opened = await ExternalDirections.open(
    ExternalDirections.googleMaps(latitude, longitude),
  );
  if (!opened && context.mounted) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        behavior: SnackBarBehavior.floating,
        content: Text('Impossible d’ouvrir Google Maps.'),
      ),
    );
  }
}
