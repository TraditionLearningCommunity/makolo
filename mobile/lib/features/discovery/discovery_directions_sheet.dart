import 'package:flutter/material.dart';

import '../../platform/maps/external_directions.dart';

/// This is a navigation *handoff*, not Makolo route planning. The route,
/// traffic, GPS and directions are owned by the user's chosen application.
Future<void> showDiscoveryDirections(
  BuildContext context, {
  required double latitude,
  required double longitude,
}) async {
  if (!ExternalDirections.valid(latitude, longitude)) return;
  final selected = await showModalBottomSheet<String>(
    context: context,
    showDragHandle: true,
    useSafeArea: true,
    builder: (sheetContext) => SafeArea(
      child: Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
              child: Text(
                'Comment y aller ?',
                style: Theme.of(sheetContext).textTheme.titleMedium,
              ),
            ),
            ListTile(
              key: const Key('discover-directions-google'),
              leading: const Icon(Icons.directions_outlined),
              title: const Text('Google Maps'),
              subtitle: const Text('Choisir votre itinéraire et votre mode de transport'),
              onTap: () => Navigator.of(sheetContext).pop('google'),
            ),
            ListTile(
              key: const Key('discover-directions-waze'),
              leading: const Icon(Icons.directions_car_outlined),
              title: const Text('Waze'),
              subtitle: const Text('Itinéraire en voiture'),
              onTap: () => Navigator.of(sheetContext).pop('waze'),
            ),
          ],
        ),
      ),
    ),
  );
  if (!context.mounted || selected == null) return;
  final uri = selected == 'google'
      ? ExternalDirections.googleMaps(latitude, longitude)
      : ExternalDirections.waze(latitude, longitude);
  final opened = await ExternalDirections.open(uri);
  if (!opened && context.mounted) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        behavior: SnackBarBehavior.floating,
        content: Text('Impossible d’ouvrir l’application d’itinéraire.'),
      ),
    );
  }
}
