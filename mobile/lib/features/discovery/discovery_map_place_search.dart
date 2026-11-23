import 'package:flutter/material.dart';

import '../../platform/location/geo_search_gateway.dart';
import '../../presentation/fields/geo_autocomplete_field.dart';

/// Reuses the same geographic autocomplete as Discovery Search. Choosing a
/// suggestion never creates a Makolo Place, Activity or user GPS fix.
Future<GeoSuggestion?> chooseDiscoveryMapPlace(
  BuildContext context, {
  required GeoSearchGateway gateway,
}) => showModalBottomSheet<GeoSuggestion>(
  context: context,
  isScrollControlled: true,
  useSafeArea: true,
  showDragHandle: true,
  builder: (_) => _MapPlaceSearchSheet(gateway: gateway),
);

class _MapPlaceSearchSheet extends StatefulWidget {
  const _MapPlaceSearchSheet({required this.gateway});
  final GeoSearchGateway gateway;

  @override
  State<_MapPlaceSearchSheet> createState() => _MapPlaceSearchSheetState();
}

class _MapPlaceSearchSheetState extends State<_MapPlaceSearchSheet> {
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Padding(
    padding: EdgeInsets.fromLTRB(
      16,
      8,
      16,
      MediaQuery.viewInsetsOf(context).bottom + 20,
    ),
    child: SingleChildScrollView(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Chercher un lieu',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 16),
          GeoAutocompleteField(
            fieldKey: const Key('discover-map-place-field'),
            controller: _controller,
            gateway: widget.gateway,
            labelText: 'Ville ou lieu',
            hintText: 'Ex. Maseru, Lubumbashi…',
            onSelected: (place) => Navigator.of(context).pop(place),
          ),
          const SizedBox(height: 8),
          Text(
            'Sélectionnez un lieu pour voir les possibilités à proximité.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    ),
  );
}
