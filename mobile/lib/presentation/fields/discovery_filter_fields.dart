import 'package:flutter/material.dart';

import '../../design/makolo_theme.dart';
import '../../platform/location/geo_search_gateway.dart';
import 'geo_autocomplete_field.dart';

/// One set of Discovery controls for public and personal explorers.
/// Authentication, search state and network acquisition stay with the caller.
class DiscoveryFilterFields extends StatelessWidget {
  const DiscoveryFilterFields({
    super.key,
    required this.keyPrefix,
    required this.placeController,
    required this.geoSearch,
    required this.when,
    required this.date,
    required this.price,
    required this.onPlaceSelected,
    required this.onPlaceEdited,
    required this.onPlaceSubmitted,
    required this.onWhenChanged,
    required this.onChooseDate,
    required this.onPriceChanged,
    this.extra,
  });

  final String keyPrefix;
  final TextEditingController placeController;
  final GeoSearchGateway? geoSearch;
  final String when;
  final String date;
  final String price;
  final ValueChanged<GeoSuggestion> onPlaceSelected;
  final VoidCallback onPlaceEdited;
  final VoidCallback onPlaceSubmitted;
  final ValueChanged<String> onWhenChanged;
  final VoidCallback onChooseDate;
  final ValueChanged<String> onPriceChanged;
  final Widget? extra;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      GeoAutocompleteField(
        fieldKey: Key('$keyPrefix-place'),
        controller: placeController,
        gateway: geoSearch,
        onSelected: onPlaceSelected,
        onEdited: onPlaceEdited,
        onSubmitted: onPlaceSubmitted,
      ),
      if (extra != null) ...[const SizedBox(height: MakoloSpacing.md), extra!],
      const SizedBox(height: MakoloSpacing.md),
      KeyedSubtree(
        // The dropdown state must track owner-driven resets, not retain a
        // previously selected value when filters are cleared.
        key: ValueKey('$keyPrefix-when-$when-$date'),
        child: DropdownButtonFormField<String>(
          key: Key('$keyPrefix-when'),
          initialValue: when,
          isExpanded: true,
          menuMaxHeight: 240,
          decoration: const InputDecoration(
            labelText: 'Quand ?',
            prefixIcon: Icon(Icons.calendar_today_outlined),
            border: OutlineInputBorder(),
          ),
          items: const [
            DropdownMenuItem(value: '', child: Text('Toutes les dates')),
            DropdownMenuItem(value: 'today', child: Text('Aujourd’hui')),
            DropdownMenuItem(value: 'tomorrow', child: Text('Demain')),
            DropdownMenuItem(value: 'weekend', child: Text('Ce week-end')),
            DropdownMenuItem(value: 'week', child: Text('Cette semaine')),
            DropdownMenuItem(value: 'custom', child: Text('Choisir une date…')),
          ],
          onChanged: (value) {
            if (value == 'custom') {
              onChooseDate();
            } else {
              onWhenChanged(value ?? '');
            }
          },
        ),
      ),
      if (date.isNotEmpty)
        TextButton.icon(
          key: Key('$keyPrefix-selected-date'),
          onPressed: onChooseDate,
          icon: const Icon(Icons.edit_calendar_outlined),
          label: Text('Date : $date'),
        ),
      const SizedBox(height: MakoloSpacing.md),
      KeyedSubtree(
        key: ValueKey('$keyPrefix-price-$price'),
        child: DropdownButtonFormField<String>(
          key: Key('$keyPrefix-price'),
          initialValue: price,
          isExpanded: true,
          menuMaxHeight: 200,
          decoration: const InputDecoration(
            labelText: 'Budget',
            prefixIcon: Icon(Icons.payments_outlined),
            border: OutlineInputBorder(),
          ),
          items: const [
            DropdownMenuItem(value: '', child: Text('Tous les prix')),
            DropdownMenuItem(value: 'free', child: Text('Gratuit')),
            DropdownMenuItem(value: 'paid', child: Text('Payant')),
          ],
          onChanged: (value) => onPriceChanged(value ?? ''),
        ),
      ),
    ],
  );
}

/// A shared vocabulary, order, icon set and selection behavior for Discovery.
class DiscoveryCategoryChips extends StatelessWidget {
  const DiscoveryCategoryChips({
    super.key,
    required this.selected,
    required this.onSelected,
    required this.listKey,
  });

  final String selected;
  final ValueChanged<String> onSelected;
  final Key listKey;

  @override
  Widget build(BuildContext context) => SizedBox(
    height: 48,
    child: ListView(
      key: listKey,
      scrollDirection: Axis.horizontal,
      children: [
        for (final category in const [
          ('', 'Tout', Icons.apps_rounded),
          ('transport', 'Voyager', Icons.directions_bus_outlined),
          ('event', 'Événements', Icons.event_outlined),
          ('service', 'Services', Icons.handshake_outlined),
          ('other', 'Autres', Icons.explore_outlined),
        ]) ...[
          ChoiceChip(
            avatar: Icon(category.$3, size: 18),
            label: Text(category.$2),
            selected: selected == category.$1,
            showCheckmark: false,
            onSelected: (_) => onSelected(category.$1),
          ),
          const SizedBox(width: MakoloSpacing.sm),
        ],
      ],
    ),
  );
}
