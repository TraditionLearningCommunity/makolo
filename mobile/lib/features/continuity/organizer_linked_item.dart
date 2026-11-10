import 'package:flutter/material.dart';

/// A navigable owner-backed child entry in the Objectives organizer.
///
/// This widget only presents the title and kind already supplied by the
/// owner projection. The caller owns permissions and destination resolution.
class OrganizerLinkedItem extends StatelessWidget {
  const OrganizerLinkedItem({
    super.key,
    required this.title,
    required this.kind,
    required this.icon,
    required this.onOpen,
    this.dense = false,
  });

  final String title;
  final String kind;
  final IconData icon;
  final VoidCallback onOpen;
  final bool dense;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Material(
      color: scheme.surfaceContainerLow,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: scheme.outlineVariant),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onOpen,
        child: Padding(
          padding: EdgeInsets.symmetric(
            horizontal: 11,
            vertical: dense ? 9 : 12,
          ),
          child: Row(
            children: [
              Icon(icon, size: 19, color: scheme.primary),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    Text(
                      kind,
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 6),
              Icon(
                Icons.chevron_right_rounded,
                color: scheme.primary,
                size: 23,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
