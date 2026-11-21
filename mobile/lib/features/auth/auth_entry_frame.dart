import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../design/makolo_mark.dart';
import '../../design/makolo_theme.dart';

/// Shared purple identity for login, signup and account recovery.
class AuthEntryFrame extends StatelessWidget {
  const AuthEntryFrame({
    super.key,
    required this.title,
    this.subtitle,
    required this.child,
    this.onBack,
    this.onClose,
    this.footer = '',
    this.compactIdentity = false,
  });

  final String title;
  final String? subtitle;
  final Widget child;
  final VoidCallback? onBack;
  final VoidCallback? onClose;
  final String footer;
  final bool compactIdentity;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final keyboardOpen = MediaQuery.viewInsetsOf(context).bottom > 0;
    final compact = MediaQuery.sizeOf(context).height < 700 || keyboardOpen;

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.light,
        statusBarBrightness: Brightness.dark,
        systemNavigationBarColor: MakoloColors.indigo,
        systemNavigationBarIconBrightness: Brightness.light,
      ),
      child: Scaffold(
        backgroundColor: MakoloColors.indigo,
        resizeToAvoidBottomInset: true,
        body: SafeArea(
          child: LayoutBuilder(
            builder: (context, constraints) {
              final horizontal = constraints.maxWidth < 360
                  ? MakoloSpacing.md
                  : MakoloSpacing.lg;
              final vertical = compact ? MakoloSpacing.sm : MakoloSpacing.lg;

              final content = SingleChildScrollView(
                keyboardDismissBehavior:
                    ScrollViewKeyboardDismissBehavior.onDrag,
                padding: EdgeInsets.symmetric(
                  horizontal: horizontal,
                  vertical: vertical,
                ),
                child: ConstrainedBox(
                  constraints: BoxConstraints(
                    minHeight: constraints.maxHeight > vertical * 2
                        ? constraints.maxHeight - vertical * 2
                        : 0.0,
                  ),
                  child: Align(
                    alignment: compactIdentity
                        ? Alignment.topCenter
                        : Alignment.center,
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 440),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          if (!compactIdentity &&
                              (onBack != null || onClose != null))
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                if (onBack != null)
                                  IconButton(
                                    tooltip: 'Retour',
                                    onPressed: onBack,
                                    color: Colors.white,
                                    icon: const Icon(Icons.arrow_back_rounded),
                                  )
                                else
                                  const SizedBox(width: 48),
                                if (onClose != null)
                                  IconButton(
                                    tooltip: 'Fermer',
                                    onPressed: onClose,
                                    color: Colors.white,
                                    icon: const Icon(Icons.close_rounded),
                                  ),
                              ],
                            ),
                          SizedBox(
                            height: compactIdentity
                                ? (compact ? MakoloSpacing.strong : 88.0)
                                : compact
                                ? MakoloSpacing.xs
                                : MakoloSpacing.md,
                          ),
                          Center(
                            child: MakoloMark(
                              size: compactIdentity
                                  ? 42
                                  : compact
                                  ? 52
                                  : 64,
                              white: true,
                            ),
                          ),
                          SizedBox(
                            height: compactIdentity
                                ? MakoloSpacing.md
                                : compact
                                ? MakoloSpacing.md
                                : MakoloSpacing.lg,
                          ),
                          Text(
                            title,
                            textAlign: TextAlign.center,
                            style: textTheme.headlineSmall?.copyWith(
                              color: Colors.white,
                              fontWeight: FontWeight.w800,
                              height: 1.18,
                            ),
                          ),
                          if (subtitle != null &&
                              subtitle!.trim().isNotEmpty) ...[
                            const SizedBox(height: MakoloSpacing.sm),
                            Text(
                              subtitle!,
                              textAlign: TextAlign.center,
                              style: textTheme.bodyLarge?.copyWith(
                                color: Colors.white.withValues(alpha: 0.90),
                                height: 1.4,
                              ),
                            ),
                          ],
                          SizedBox(
                            height: compactIdentity
                                ? MakoloSpacing.lg
                                : compact
                                ? MakoloSpacing.lg
                                : MakoloSpacing.xl,
                          ),
                          child,
                          if (!keyboardOpen && footer.isNotEmpty) ...[
                            const SizedBox(height: MakoloSpacing.xl),
                            Text(
                              footer,
                              textAlign: TextAlign.center,
                              style: textTheme.bodySmall?.copyWith(
                                color: Colors.white.withValues(alpha: 0.74),
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                          const SizedBox(height: MakoloSpacing.md),
                        ],
                      ),
                    ),
                  ),
                ),
              );
              if (!compactIdentity) return content;
              return DecoratedBox(
                decoration: const BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      MakoloColors.indigo,
                      Color(0xFF4727C4),
                      MakoloColors.deep,
                    ],
                  ),
                ),
                child: Stack(
                  children: [
                    Positioned.fill(child: content),
                    if (onClose != null)
                      Positioned(
                        top: MakoloSpacing.xs,
                        right: MakoloSpacing.sm,
                        child: IconButton.filledTonal(
                          key: const Key('account-chooser-close'),
                          tooltip: 'Fermer',
                          onPressed: onClose,
                          style: IconButton.styleFrom(
                            backgroundColor: Colors.white.withValues(
                              alpha: 0.16,
                            ),
                            foregroundColor: Colors.white,
                            minimumSize: const Size(48, 48),
                          ),
                          icon: const Icon(Icons.close_rounded),
                        ),
                      ),
                  ],
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}
