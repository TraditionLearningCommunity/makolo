import 'package:flutter/material.dart';

/// Project description used by the same workspace for Profile and Space.
///
/// No presentation title, fabricated summary, or server-owned business state.
/// Text is folded only when it exceeds [collapsedLines] at the actual width.
class ProjectDescription extends StatefulWidget {
  const ProjectDescription({
    super.key,
    required this.description,
    this.collapsedLines = 3,
  });

  final String? description;
  final int collapsedLines;

  @override
  State<ProjectDescription> createState() => _ProjectDescriptionState();
}

class _ProjectDescriptionState extends State<ProjectDescription> {
  bool _expanded = false;

  @override
  void didUpdateWidget(covariant ProjectDescription oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.description != widget.description) {
      _expanded = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = widget.description?.trim() ?? '';
    if (text.isEmpty) return const SizedBox.shrink();

    final scheme = Theme.of(context).colorScheme;
    final style = Theme.of(context).textTheme.bodyMedium
        ?.copyWith(height: 1.45, color: scheme.onSurfaceVariant);
    final direction = Directionality.of(context);
    final scale = MediaQuery.textScalerOf(context);

    return LayoutBuilder(
      builder: (context, constraints) {
        final painter = TextPainter(
          text: TextSpan(text: text, style: style),
          textDirection: direction,
          textScaler: scale,
          maxLines: widget.collapsedLines,
        )..layout(maxWidth: constraints.maxWidth - 32);

        final canExpand = painter.didExceedMaxLines;
        painter.dispose();

        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.only(top: 2, right: 10),
              child: Icon(
                Icons.info_outline_rounded,
                size: 20,
                color: scheme.primary,
              ),
            ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    text,
                    style: style,
                    maxLines: canExpand && !_expanded
                        ? widget.collapsedLines
                        : null,
                    overflow: canExpand && !_expanded
                        ? TextOverflow.ellipsis
                        : TextOverflow.visible,
                  ),
                  if (canExpand)
                    Align(
                      alignment: AlignmentDirectional.centerEnd,
                      child: IconButton(
                        tooltip: _expanded
                            ? 'Replier les informations'
                            : 'Lire toutes les informations',
                        onPressed: () => setState(() => _expanded = !_expanded),
                        icon: Icon(
                          _expanded
                              ? Icons.keyboard_arrow_up_rounded
                              : Icons.keyboard_arrow_down_rounded,
                        ),
                        visualDensity: VisualDensity.compact,
                      ),
                    ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}
