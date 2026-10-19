import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../../design/makolo_theme.dart';
import '../../network/makolo_api_client.dart';
import '../../features/discovery/discovery_share_sheet.dart';
import '../../features/discovery/discovery_selector.dart';

/// The existing Discovery projection rendered as one N1 unit.
/// Facts and actions remain owned by the server; this widget only composes.
class DiscoveryOrbitIcon extends StatelessWidget {
  const DiscoveryOrbitIcon({
    super.key,
    required this.saved,
    required this.color,
  });

  final bool saved;
  final Color color;

  static const _orbitAvailable = '''
<svg viewBox="0 0 24 24"><path d="M5.2 17.6A8.7 8.7 0 0 1 16.9 5.1" fill="none" stroke="#000" stroke-width="2.2" stroke-linecap="round"/><path d="M18.4 7.2a8.6 8.6 0 0 1 .2 7.4" fill="none" stroke="#000" stroke-width="2.2" stroke-linecap="round"/><circle cx="19.3" cy="17.6" r="1.45" fill="#000"/></svg>
''';
  static const _orbitSaved = '''
<svg viewBox="0 0 24 24"><path d="M5.6 17.2a8.2 8.2 0 1 1 12.9-1.4" fill="none" stroke="#000" stroke-width="2.4" stroke-linecap="round"/><circle cx="12" cy="12" r="3.2" fill="#000"/><circle cx="19.2" cy="17.5" r="1.55" fill="#000"/></svg>
''';

  @override
  Widget build(BuildContext context) {
    return SvgPicture.string(
      saved ? _orbitSaved : _orbitAvailable,
      width: 21,
      height: 21,
      colorFilter: ColorFilter.mode(color, BlendMode.srcIn),
      semanticsLabel: saved ? 'Enregistré' : 'Enregistrer',
    );
  }
}

class DiscoveryPossibilityUnit extends StatefulWidget {
  const DiscoveryPossibilityUnit({
    super.key,
    required this.item,
    required this.onOpen,
    this.onSave,
    this.allowSavePrompt = false,
    this.shareApi,
    this.shareAuthenticated = false,
    this.onSignIn,
    this.onSelect,
    this.selectionActionLabel,
    this.baseUri,
    this.compact = false,
  });

  final DiscoveryItemPresentation item;
  final VoidCallback onOpen;
  final Future<void> Function()? onSave;
  final bool allowSavePrompt;
  final MakoloApiClient? shareApi;
  final bool shareAuthenticated;
  final VoidCallback? onSignIn;
  final VoidCallback? onSelect;
  final String? selectionActionLabel;
  final Uri? baseUri;
  final bool compact;

  @override
  State<DiscoveryPossibilityUnit> createState() =>
      _DiscoveryPossibilityUnitState();
}

class _DiscoveryPossibilityUnitState extends State<DiscoveryPossibilityUnit> {
  bool _saving = false;
  bool? _confirmedSaved;

  @override
  void didUpdateWidget(covariant DiscoveryPossibilityUnit oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.item.candidateKey != widget.item.candidateKey ||
        (_confirmedSaved != null &&
            widget.item.savedState ==
                (_confirmedSaved! ? 'saved' : 'not_saved'))) {
      _confirmedSaved = null;
    }
  }

  Future<void> _save() async {
    if (_saving || widget.onSave == null) return;
    final previousState = widget.item.savedState;
    setState(() => _saving = true);
    try {
      await widget.onSave!();
      if (mounted &&
          !widget.allowSavePrompt &&
          widget.item.savedState == previousState) {
        setState(() => _confirmedSaved = previousState != 'saved');
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('L’enregistrement n’a pas pu être confirmé.'),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  DiscoveryItemPresentation get item => widget.item;

  List<Map<String, dynamic>> get _reliableFacts {
    final facts = <Map<String, dynamic>>[];
    final seen = <String>{};

    void add(String code, String label, String? value) {
      if (value == null || value.trim().isEmpty || !seen.add(code)) return;
      facts.add({'code': code, 'label': label, 'value': value});
    }

    for (final fact in item.presentationFacts) {
      final label = fact['label'];
      final value = fact['value'];
      if (label is String && value is String) {
        add((fact['code'] ?? label).toString(), label, value);
      }
    }
    add('price', 'Prix', item.price);
    add('when', 'Quand', item.timing);
    add('place', 'Lieu', item.place);
    add('capacity', 'Disponibilité', item.availability);
    add('route', 'Trajet', item.routeLabel);
    const dates = {
      'start_at': 'Début',
      'end_at': 'Fin',
      'start_date': 'Début',
      'end_date': 'Fin',
      'opens_at': 'Ouverture',
      'closes_at': 'Clôture',
      'deadline_at': 'Date limite',
    };
    for (final fact in item.temporalFacts) {
      final kind = fact['kind']?.toString() ?? '';
      final label = dates[kind];
      if (kind.startsWith('start_') && seen.contains('when')) continue;
      if (label != null) add(kind, label, fact['value']?.toString());
    }
    for (final fact in item.spatialFacts) {
      final role = fact['role']?.toString() ?? '';
      if (role == 'primary' && seen.contains('place')) continue;
      final place = fact['place'];
      if (place is Map) {
        add(
          'place_$role',
          role.isEmpty ? 'Lieu' : role,
          place['name']?.toString(),
        );
      }
    }
    return facts;
  }

  List<String> get _resourceLabels {
    final labels = <String>[];
    final resources = item.wire['resources'];
    if (resources is List) {
      for (final raw in resources) {
        if (raw is! Map) continue;
        final title = (raw['title'] ?? '').toString().trim();
        if (title.isEmpty) continue;
        final mime = (raw['mime_type'] ?? '').toString().toLowerCase();
        final format = mime.contains('pdf')
            ? 'PDF'
            : mime.contains('spreadsheet') || mime.contains('excel')
            ? 'Tableur'
            : mime.startsWith('video/')
            ? 'Vidéo'
            : mime.startsWith('audio/')
            ? 'Audio'
            : raw['kind'] == 'file'
            ? 'Document'
            : 'Source';
        labels.add('$format · $title');
      }
    }
    for (final binding in item.mediaBindings) {
      final resource = binding['resource'];
      if (resource is! Map) continue;
      final mime = (resource['mime_type'] ?? binding['mime_type'] ?? '')
          .toString()
          .toLowerCase();
      final name = (resource['name'] ?? resource['title'] ?? '')
          .toString()
          .trim();
      final format = mime.contains('pdf')
          ? 'PDF'
          : mime.contains('spreadsheet') || mime.contains('excel')
          ? 'Tableur'
          : mime.startsWith('video/')
          ? 'Vidéo'
          : mime.startsWith('audio/')
          ? 'Audio'
          : mime.contains('document')
          ? 'Document'
          : null;
      if (format != null) labels.add(name.isEmpty ? format : '$format · $name');
    }
    return labels;
  }

  Widget _media(BuildContext context) {
    final uri = item.imageUrl == null ? null : Uri.tryParse(item.imageUrl!);
    final validImage =
        uri != null &&
        (uri.scheme == 'https' || uri.scheme == 'http') &&
        uri.host.isNotEmpty;
    if (!validImage) return const SizedBox.shrink();
    return AspectRatio(
      aspectRatio: 4 / 3,
      child: Image.network(
        item.imageUrl!,
        fit: BoxFit.cover,
        semanticLabel: 'Visuel de ${item.title}',
        errorBuilder: (_, _, _) => const SizedBox.shrink(),
      ),
    );
  }

  Widget _facts(BuildContext context) {
    final facts = _reliableFacts;
    if (facts.isEmpty) return const SizedBox.shrink();
    return Wrap(
      spacing: MakoloSpacing.md,
      runSpacing: MakoloSpacing.sm,
      children: [
        for (final fact in facts)
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 180),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  fact['label'] as String,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
                Text(
                  fact['value'] as String,
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ],
            ),
          ),
      ],
    );
  }

  Widget _knowledge(BuildContext context) {
    final significant = item.assessment
        .where((fact) {
          return fact['state'] == 'favorable' ||
              fact['state'] == 'limiting' ||
              fact['state'] == 'unknown';
        })
        .take(3);
    if (significant.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final fact in significant)
          if (fact['label'] is String && (fact['label'] as String).isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: MakoloSpacing.xs),
              child: Text(
                fact['label'] as String,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final saved = _confirmedSaved ?? (item.savedState == 'saved');
    final canToggle =
        _confirmedSaved == null && (saved ? item.canUnsave : item.canSave);

    final resources = _resourceLabels;
    return DecoratedBox(
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(color: theme.colorScheme.outlineVariant),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (!widget.compact) _media(context),
          InkWell(
            onTap: widget.onOpen,
            child: Padding(
              padding: EdgeInsets.all(
                widget.compact ? MakoloSpacing.sm : MakoloSpacing.md,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (item.eyebrow != null && item.eyebrow!.trim().isNotEmpty)
                    Text(
                      item.eyebrow!,
                      style: theme.textTheme.labelMedium?.copyWith(
                        color: theme.colorScheme.primary,
                      ),
                    ),
                  const SizedBox(height: MakoloSpacing.xs),
                  Text(
                    item.title,
                    style: widget.compact
                        ? theme.textTheme.titleSmall
                        : theme.textTheme.titleMedium,
                  ),
                  if (item.owner != null) ...[
                    const SizedBox(height: MakoloSpacing.xs),
                    Text(item.owner!, style: theme.textTheme.labelMedium),
                  ],
                  if (item.summary.trim().isNotEmpty) ...[
                    const SizedBox(height: MakoloSpacing.sm),
                    Text(
                      item.summary,
                      style: widget.compact
                          ? theme.textTheme.bodySmall
                          : theme.textTheme.bodyMedium,
                    ),
                  ],
                  if (item.detailFacts?['description'] is String &&
                      (item.detailFacts!['description'] as String)
                          .trim()
                          .isNotEmpty &&
                      item.detailFacts!['description'] != item.summary) ...[
                    const SizedBox(height: MakoloSpacing.sm),
                    Text(item.detailFacts!['description'] as String),
                  ],
                  if (item.participantPresentation?['label'] is String &&
                      (item.participantPresentation!['label'] as String)
                          .isNotEmpty) ...[
                    const SizedBox(height: MakoloSpacing.sm),
                    Text(
                      item.participantPresentation!['label'] as String,
                      style: theme.textTheme.labelMedium,
                    ),
                  ],
                  if (resources.isNotEmpty) ...[
                    const SizedBox(height: MakoloSpacing.sm),
                    for (final resource in resources)
                      Padding(
                        padding: const EdgeInsets.only(
                          bottom: MakoloSpacing.xs,
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.description_outlined, size: 18),
                            const SizedBox(width: MakoloSpacing.xs),
                            Expanded(
                              child: Text(
                                resource,
                                style: theme.textTheme.bodySmall,
                              ),
                            ),
                          ],
                        ),
                      ),
                  ],
                  const SizedBox(height: MakoloSpacing.md),
                  _facts(context),
                  _knowledge(context),
                  if (item.variants.isNotEmpty ||
                      item.relations.isNotEmpty) ...[
                    const SizedBox(height: MakoloSpacing.sm),
                    Text(
                      [
                        if (item.variants.isNotEmpty)
                          '${item.variants.length} variantes',
                        if (item.relations.isNotEmpty)
                          '${item.relations.length} relations',
                      ].join(' · '),
                      style: theme.textTheme.bodySmall,
                    ),
                  ],
                ],
              ),
            ),
          ),
          ...[
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: MakoloSpacing.xs,
                vertical: MakoloSpacing.xs,
              ),
              child: Row(
                children: [
                  Expanded(
                    child: TextButton(
                      onPressed:
                          !_saving &&
                              widget.onSave != null &&
                              (canToggle || widget.allowSavePrompt)
                          ? _save
                          : null,
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          DiscoveryOrbitIcon(
                            saved: saved,
                            color: theme.colorScheme.primary,
                          ),
                          const SizedBox(height: 3),
                          Text(
                            _saving
                                ? 'Enregistrement…'
                                : saved
                                ? 'Enregistré'
                                : 'J’enregistre',
                            textAlign: TextAlign.center,
                          ),
                        ],
                      ),
                    ),
                  ),
                  Expanded(
                    child: TextButton(
                      onPressed: widget.onOpen,
                      child: const Text(
                        'Voir plus',
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ),
                  Expanded(
                    child: DiscoveryShareControl(
                      item: item,
                      api: widget.shareApi,
                      authenticated: widget.shareAuthenticated,
                      onSignIn: widget.onSignIn,
                    ),
                  ),
                ],
              ),
            ),
          ],
          if (widget.onSelect != null)
            TextButton.icon(
              key: ValueKey('discover-map-action-${widget.item.candidateKey}'),
              onPressed: widget.onSelect,
              icon: const Icon(Icons.map_outlined),
              label: Text(widget.selectionActionLabel ?? 'Voir sur la carte'),
            ),
        ],
      ),
    );
  }
}
