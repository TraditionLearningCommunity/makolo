import 'package:flutter/material.dart';

import '../../design/makolo_theme.dart';

class MakoloAuthField extends StatelessWidget {
  const MakoloAuthField({
    super.key,
    required this.label,
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
    this.onFieldSubmitted,
    this.onEditingComplete,
  });

  final String label;
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
  final ValueChanged<String>? onFieldSubmitted;
  final VoidCallback? onEditingComplete;

  @override
  Widget build(BuildContext context) {
    final border = OutlineInputBorder(
      borderRadius: BorderRadius.circular(18),
      borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.22)),
    );
    return TextFormField(
      key: fieldKey,
      controller: controller,
      focusNode: focusNode,
      enabled: enabled,
      keyboardType: keyboardType,
      textInputAction: textInputAction,
      autofillHints: autofillHints,
      obscureText: obscureText,
      validator: validator,
      autovalidateMode: AutovalidateMode.onUserInteraction,
      onFieldSubmitted: onFieldSubmitted,
      onEditingComplete: onEditingComplete,
      style: const TextStyle(
        color: MakoloColors.ink,
        fontSize: 17,
        fontWeight: FontWeight.w500,
      ),
      decoration: InputDecoration(
        labelText: label,
        floatingLabelBehavior: FloatingLabelBehavior.always,
        labelStyle: TextStyle(color: MakoloColors.deep.withValues(alpha: 0.72)),
        floatingLabelStyle: const TextStyle(
          color: MakoloColors.deep,
          fontWeight: FontWeight.w700,
        ),
        prefixIcon: prefixIcon == null
            ? null
            : Icon(prefixIcon, color: MakoloColors.deep),
        suffixIcon: suffixIcon,
        filled: true,
        fillColor: MakoloColors.warm,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: MakoloSpacing.md,
          vertical: 18,
        ),
        border: border,
        enabledBorder: border,
        disabledBorder: border,
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(18),
          borderSide: const BorderSide(color: Colors.white, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(18),
          borderSide: const BorderSide(color: Color(0xFFFFB4AB), width: 1.5),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(18),
          borderSide: const BorderSide(color: Color(0xFFFFDAD6), width: 2),
        ),
        errorStyle: const TextStyle(
          color: Color(0xFFFFDAD6),
          fontWeight: FontWeight.w600,
        ),
      ),
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
        foregroundColor: MakoloColors.indigo,
        disabledBackgroundColor: Colors.white.withValues(alpha: 0.62),
        disabledForegroundColor: MakoloColors.indigo.withValues(alpha: 0.7),
        minimumSize: const Size.fromHeight(56),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        textStyle: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800),
      ),
      child: busy
          ? const SizedBox(
              width: 22,
              height: 22,
              child: CircularProgressIndicator(
                strokeWidth: 2.5,
                color: MakoloColors.indigo,
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
        side: BorderSide(color: Colors.white.withValues(alpha: 0.72)),
        minimumSize: const Size.fromHeight(54),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
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
    return Semantics(
      container: true,
      label: 'Se souvenir de moi',
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onChanged == null ? null : () => onChanged!(!value),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.xs),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Checkbox(
                value: value,
                onChanged: onChanged == null
                    ? null
                    : (checked) => onChanged!(checked ?? false),
                side: const BorderSide(color: Colors.white, width: 1.5),
                checkColor: MakoloColors.indigo,
                fillColor: WidgetStateProperty.resolveWith(
                  (states) => states.contains(WidgetState.selected)
                      ? Colors.white
                      : Colors.transparent,
                ),
              ),
              const SizedBox(width: MakoloSpacing.xs),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: const Text(
                    'Se souvenir de moi',
                    style: TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
