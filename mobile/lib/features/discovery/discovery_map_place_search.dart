import 'package:flutter/material.dart';

import '../../platform/location/geo_search_gateway.dart';
import '../../presentation/fields/geo_autocomplete_field.dart';

/// Reuses the same geographic autocomplete as Discovery Search. Choosing a
/// suggestion does not create a Makolo Place, Activity or user location fix.
Future<GeoSuggestion?> chooseDiscoveryMapPlace(
  BuildContext context, {
  required GeoSearchGateway gateway,
}) async {
  final controller = TextEditingController();
  try {
    return await showModalBottomSheet<GeoSuggestion>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      builder: (sheetContext) => Padding(
        padding: EdgeInsets.fromLTRB(
          16,
          8,
          16,
          MediaQuery.viewInsetsOf(sheetContext).bottom + 20,
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Chercher un lieu',
                style: Theme.of(sheetContext).textTheme.titleMedium,
              ),
              const SizedBox(height: 16),
              GeoAutocompleteField(
                fieldKey: const Key('discover-map-place-field'),
                controller: controller,
                gateway: gateway,
                labelText: 'Ville ou lieu',
                hintText: 'Ex. Maseru, Lubumbashi…',
                onSelected: (place) =>
                    Navigator.of(sheetContext).pop(place),
              ),
              const SizedBox(height: 8),
              Text(
                'Sélectionnez un lieu pour voir les possibilités à proximité.',
                style: Theme.of(sheetContext).textTheme.bodySmall,
              ),
            ],
          ),
        ),
      ),
    );
  } finally {
    controller.dispose();
  }
}
