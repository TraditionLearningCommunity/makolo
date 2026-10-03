import 'package:flutter/material.dart';

import '../../design/makolo_mark.dart';
import '../../design/makolo_theme.dart';
import 'mps_models.dart';

class MpsNativeRenderer extends StatelessWidget {
  const MpsNativeRenderer({
    super.key,
    required this.package,
    this.onOpenCredential,
  });

  static const rendererVersion = 1;

  final MpsPresentationPackage package;
  final VoidCallback? onOpenCredential;

  @override
  Widget build(BuildContext context) {
    final effectiveManifest =
        package.artifact.minimumRendererVersion > rendererVersion
        ? mpsEssentialManifest
        : package.manifest;
    final layout = mpsMap(effectiveManifest['layout']);
    final palette = _MpsPalette.fromTokens(package.themeTokens, context);

    return ColoredBox(
      color: palette.background,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(MakoloSpacing.inner),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(
              maxWidth: MakoloLayout.readingMaxWidth,
            ),
            child: _node(context, layout, palette),
          ),
        ),
      ),
    );
  }

  Widget _node(
    BuildContext context,
    Map<String, dynamic> node,
    _MpsPalette palette,
  ) {
    final name = mpsString(node['component']);
    if (name == null) return const SizedBox.shrink();
    final props = mpsMap(node['props']);
    final children = node['children'] is List
        ? (node['children'] as List)
              .map(mpsMap)
              .where((child) => child.isNotEmpty)
              .map((child) => _node(context, child, palette))
              .toList(growable: false)
        : const <Widget>[];

    switch (name) {
      case 'Page':
      case 'Section':
      case 'Stack':
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: _withSpacing(children),
        );
      case 'Grid':
        return Wrap(
          spacing: MakoloSpacing.md,
          runSpacing: MakoloSpacing.md,
          children: children
              .map((child) => SizedBox(width: 280, child: child))
              .toList(growable: false),
        );
      case 'MakoloMark':
        return const Align(
          alignment: Alignment.centerLeft,
          child: MakoloMark(
            size: 42,
            semantics: MakoloMarkSemantics.decorative,
          ),
        );
      case 'Heading':
        final level = props['level'] is int ? props['level'] as int : 1;
        return Text(
          _value(props['value']),
          style: level <= 1
              ? Theme.of(context).textTheme.headlineMedium?.copyWith(
                    color: palette.text,
                    fontWeight: FontWeight.w800,
                  )
              : Theme.of(context).textTheme.titleLarge?.copyWith(
                    color: palette.text,
                    fontWeight: FontWeight.w700,
                  ),
        );
      case 'Subheading':
        return Text(
          _value(props['value']),
          style: Theme.of(
            context,
          ).textTheme.titleMedium?.copyWith(color: palette.muted),
        );
      case 'Text':
      case 'Footer':
        final value = _value(props['value']);
        if (value.isEmpty) return const SizedBox.shrink();
        return Text(
          value,
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
            color: name == 'Footer' ? palette.muted : palette.text,
          ),
        );
      case 'OccurrenceDetails':
        final occurrence = mpsMap(package.artifact.context['occurrence']);
        final values = <String>[
          if (mpsString(occurrence['starts_at']) case final value?) value,
          if (mpsString(occurrence['place']) case final value?) value,
        ];
        return values.isEmpty
            ? const SizedBox.shrink()
            : _InfoBlock(
                icon: Icons.event_rounded,
                lines: values,
                palette: palette,
              );
      case 'DateTime':
        return Text(
          mpsString(
                mpsMap(package.artifact.context['occurrence'])['starts_at'],
              ) ??
              '',
        );
      case 'Place':
        return Text(
          mpsString(mpsMap(package.artifact.context['occurrence'])['place']) ??
              '',
        );
      case 'Organizer':
        final value = mpsString(
          mpsMap(package.artifact.context['organizer'])['display_name'],
        );
        return value == null
            ? const SizedBox.shrink()
            : Text(
                value,
                style: Theme.of(
                  context,
                ).textTheme.titleMedium?.copyWith(color: palette.text),
              );
      case 'AccessSummary':
        final access = mpsMap(package.artifact.context['access']);
        final type = mpsString(access['display_type']);
        if (type == null) return const SizedBox.shrink();
        return _InfoBlock(
          icon: Icons.confirmation_number_outlined,
          lines: [
            type,
            if (mpsString(access['beneficiary']) case final value?) value,
            if (mpsString(access['display_status']) case final value?) value,
          ],
          palette: palette,
        );
      case 'QRCode':
        if (!package.artifact.canOpenCredential || onOpenCredential == null) {
          return const SizedBox.shrink();
        }
        return FilledButton.icon(
          onPressed: onOpenCredential,
          icon: const Icon(Icons.qr_code_2_rounded),
          label: const Text('Afficher le QR'),
        );
      case 'CallToAction':
        final label = _value(props['label']);
        return label.isEmpty
            ? const SizedBox.shrink()
            : FilledButton(onPressed: null, child: Text(label));
      case 'Divider':
        return Divider(color: palette.muted.withValues(alpha: .3));
      case 'Hero':
      case 'Image':
      case 'OrganizerMark':
        return AspectRatio(
          aspectRatio: 16 / 9,
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: palette.surface,
              borderRadius: BorderRadius.circular(MakoloRadii.card),
            ),
            child: Icon(
              Icons.image_outlined,
              color: palette.muted,
              semanticLabel: mpsString(props['alt']) ?? 'Image de présentation',
            ),
          ),
        );
      default:
        return const SizedBox.shrink();
    }
  }

  String _value(Object? raw) {
    if (raw is Map) {
      final binding = mpsString(raw['binding']);
      if (binding != null) return _binding(binding);
    }
    return mpsString(raw) ?? '';
  }

  String _binding(String binding) {
    final index = binding.indexOf('.');
    if (index <= 0 || index == binding.length - 1) return '';
    final section = binding.substring(0, index);
    final key = binding.substring(index + 1);
    return mpsString(mpsMap(package.artifact.context[section])[key]) ?? '';
  }

  static List<Widget> _withSpacing(List<Widget> children) {
    final result = <Widget>[];
    for (var index = 0; index < children.length; index++) {
      if (index > 0) result.add(const SizedBox(height: MakoloSpacing.md));
      result.add(children[index]);
    }
    return result;
  }
}

class _InfoBlock extends StatelessWidget {
  const _InfoBlock({
    required this.icon,
    required this.lines,
    required this.palette,
  });

  final IconData icon;
  final List<String> lines;
  final _MpsPalette palette;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: palette.surface,
        borderRadius: BorderRadius.circular(MakoloRadii.card),
        border: Border.all(color: palette.muted.withValues(alpha: .22)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(MakoloSpacing.md),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: palette.accent),
            const SizedBox(width: MakoloSpacing.compact),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (final line in lines)
                    Padding(
                      padding: const EdgeInsets.only(bottom: MakoloSpacing.xs),
                      child: Text(
                        line,
                        style: Theme.of(
                          context,
                        ).textTheme.bodyMedium?.copyWith(color: palette.text),
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MpsPalette {
  const _MpsPalette({
    required this.background,
    required this.surface,
    required this.text,
    required this.muted,
    required this.accent,
  });

  final Color background;
  final Color surface;
  final Color text;
  final Color muted;
  final Color accent;

  factory _MpsPalette.fromTokens(
    Map<String, dynamic> tokens,
    BuildContext context,
  ) {
    Color parse(String key, Color fallback) {
      final raw = mpsString(tokens[key]);
      if (raw == null || !RegExp(r'^#[0-9A-Fa-f]{6}$').hasMatch(raw)) {
        return fallback;
      }
      return Color(int.parse('FF' + raw.substring(1), radix: 16));
    }

    final scheme = Theme.of(context).colorScheme;
    return _MpsPalette(
      background: parse('background', scheme.surface),
      surface: parse('surface', scheme.surfaceContainerLow),
      text: parse('text', scheme.onSurface),
      muted: parse('muted', scheme.onSurfaceVariant),
      accent: parse('accent', scheme.primary),
    );
  }
}
