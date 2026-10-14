import 'package:flutter/material.dart';

import '../../design/makolo_theme.dart';

/// Input shared across the Makolo authentication journey.
/// Labels are placed outside the field to prevent outlined-border overlap.
class MakoloAuthField extends StatelessWidget {
  const MakoloAuthField({
    super.key,
    required this.label,
    this.hint,
    this.fieldKey,
    this.controller,
    this.focusNode,
    this.keyboardType,
    this.textInputAction,
    this.autofillHints,
    this.obscureText = false,
    this.enabled = true,
    this.prefixIcon,
    this.suffixIcon,
    this.validator,
    this.onChanged,
    this.onFieldSubmitted,
    this.onEditingComplete,
  });

  final String label;
  final String? hint;
  final Key? fieldKey;
  final TextEditingController? controller;
  final FocusNode? focusNode;
  final TextInputType? keyboardType;
  final TextInputAction? textInputAction;
  final Iterable<String>? autofillHints;
  final bool obscureText;
  final bool enabled;
  final IconData? prefixIcon;
  final Widget? suffixIcon;
  final String? Function(String?)? validator;
  final ValueChanged<String>? onChanged;
  final ValueChanged<String>? onFieldSubmitted;
  final VoidCallback? onEditingComplete;

  @override
  Widget build(BuildContext context) {
    const fieldColor = MakoloColors.warm;
    const contentColor = MakoloColors.ink;
    const iconColor = MakoloColors.deep;
    const placeholderColor = MakoloColors.lightMuted;

    OutlineInputBorder outline(Color color, double width) => OutlineInputBorder(
      borderRadius: BorderRadius.circular(MakoloRadii.card),
      borderSide: BorderSide(color: color, width: width),
    );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          label,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 14,
            fontWeight: FontWeight.w700,
            height: 1.4,
          ),
        ),
        const SizedBox(height: MakoloSpacing.sm),
        Semantics(
          label: label,
          child: TextFormField(
            key: fieldKey,
            controller: controller,
            focusNode: focusNode,
            enabled: enabled,
            keyboardType: keyboardType,
            textInputAction: textInputAction,
            autofillHints: autofillHints,
            obscureText: obscureText,
            autocorrect: false,
            enableSuggestions: !obscureText,
            textCapitalization: TextCapitalization.none,
            smartDashesType: SmartDashesType.disabled,
            smartQuotesType: SmartQuotesType.disabled,
            validator: validator,
            autovalidateMode: AutovalidateMode.onUserInteraction,
            onChanged: onChanged,
            onFieldSubmitted: onFieldSubmitted,
            onEditingComplete: onEditingComplete,
            onTapOutside: (_) => FocusManager.instance.primaryFocus?.unfocus(),
            cursorColor: MakoloColors.indigo,
            style: TextStyle(
              color: contentColor,
              fontSize: 16,
              fontWeight: FontWeight.w500,
            ),
            decoration: InputDecoration(
              hint: hint == null
                  ? null
                  : Text(
                      hint!,
                      softWrap: true,
                      style: const TextStyle(
                        color: placeholderColor,
                        fontSize: 15,
                      ),
                    ),
              prefixIcon: prefixIcon == null
                  ? null
                  : Icon(prefixIcon, size: 22, color: iconColor),
              suffixIcon: suffixIcon,
              filled: true,
              fillColor: fieldColor,
              contentPadding: const EdgeInsets.symmetric(
                horizontal: MakoloSpacing.md,
                vertical: MakoloSpacing.md,
              ),
              border: outline(Colors.white.withValues(alpha: 0.38), 1),
              enabledBorder: outline(Colors.white.withValues(alpha: 0.38), 1),
              disabledBorder: outline(Colors.white.withValues(alpha: 0.18), 1),
              focusedBorder: outline(MakoloColors.deep, 2),
              errorBorder: outline(const Color(0xFFFFDAD6), 2),
              focusedErrorBorder: outline(const Color(0xFFFFDAD6), 2),
              errorStyle: const TextStyle(
                color: Colors.white,
                fontSize: 12,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class MakoloAuthPrimaryButton extends StatelessWidget {
  const MakoloAuthPrimaryButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.buttonKey,
    this.busy = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final Key? buttonKey;
  final bool busy;

  @override
  Widget build(BuildContext context) {
    return FilledButton(
      key: buttonKey,
      onPressed: busy ? null : onPressed,
      style: FilledButton.styleFrom(
        backgroundColor: Colors.white,
        foregroundColor: MakoloColors.deep,
        disabledBackgroundColor: Colors.white.withValues(alpha: 0.65),
        disabledForegroundColor: MakoloColors.deep,
        minimumSize: const Size.fromHeight(56),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(MakoloRadii.card),
        ),
        textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
      ),
      child: busy
          ? Semantics(
              label: 'Traitement en cours',
              child: const SizedBox(
                width: 22,
                height: 22,
                child: CircularProgressIndicator(
                  strokeWidth: 2.5,
                  color: MakoloColors.deep,
                ),
              ),
            )
          : Text(label),
    );
  }
}

class MakoloAuthTextAction extends StatelessWidget {
  const MakoloAuthTextAction({
    super.key,
    required this.label,
    required this.onPressed,
    this.buttonKey,
    this.underline = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final Key? buttonKey;
  final bool underline;

  @override
  Widget build(BuildContext context) {
    return TextButton(
      key: buttonKey,
      onPressed: onPressed,
      style: TextButton.styleFrom(
        foregroundColor: Colors.white,
        textStyle: TextStyle(
          fontWeight: FontWeight.w700,
          decoration: underline ? TextDecoration.underline : null,
          decorationColor: Colors.white,
        ),
      ),
      child: Text(label),
    );
  }
}

class MakoloAuthSecondaryButton extends StatelessWidget {
  const MakoloAuthSecondaryButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.buttonKey,
  });

  final String label;
  final VoidCallback? onPressed;
  final Key? buttonKey;

  @override
  Widget build(BuildContext context) {
    return OutlinedButton(
      key: buttonKey,
      onPressed: onPressed,
      style: OutlinedButton.styleFrom(
        foregroundColor: Colors.white,
        side: BorderSide(color: Colors.white.withValues(alpha: 0.78)),
        minimumSize: const Size.fromHeight(54),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(MakoloRadii.card),
        ),
        textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
      ),
      child: Text(label),
    );
  }
}

class MakoloQuickAccessChoice extends StatelessWidget {
  const MakoloQuickAccessChoice({
    super.key,
    required this.value,
    required this.onChanged,
  });

  final bool value;
  final ValueChanged<bool>? onChanged;

  @override
  Widget build(BuildContext context) {
    return CheckboxListTile(
      value: value,
      onChanged: onChanged == null
          ? null
          : (checked) => onChanged!(checked ?? false),
      activeColor: Colors.white,
      checkColor: MakoloColors.deep,
      side: const BorderSide(color: Colors.white, width: 1.5),
      controlAffinity: ListTileControlAffinity.leading,
      contentPadding: EdgeInsets.zero,
      visualDensity: VisualDensity.compact,
      title: const Text(
        'Se souvenir de moi',
        style: TextStyle(
          color: Colors.white,
          fontSize: 14,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}
