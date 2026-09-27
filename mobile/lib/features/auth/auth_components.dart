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
      borderSide: BorderSide(
        color: Colors.white.withValues(alpha: 0.22),
      ),
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
        labelStyle: TextStyle(
          color: MakoloColors.deep.withValues(alpha: 0.72),
        ),
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
          borderSide: const BorderSide(
            color: Colors.white,
            width: 2,
          ),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(18),
          borderSide: const BorderSide(
            color: Color(0xFFFFB4AB),
            width: 1.5,
          ),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(18),
          borderSide: const BorderSide(
            color: Color(0xFFFFDAD6),
            width: 2,
          ),
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
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
        ),
        textStyle: const TextStyle(
          fontSize: 17,
          fontWeight: FontWeight.w800,
        ),
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
  });

  final String label;
  final VoidCallback? onPressed;
  final Key? buttonKey;

  @override
  Widget build(BuildContext context) {
    return TextButton(
      key: buttonKey,
      onPressed: onPressed,
      style: TextButton.styleFrom(
        foregroundColor: Colors.white,
        textStyle: const TextStyle(fontWeight: FontWeight.w700),
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
      label: 'Accès rapide sur cet appareil',
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
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Accès rapide sur cet appareil',
                        style: TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        'Makolo peut garder une session sécurisée pour ce compte. Votre mot de passe n’est jamais stocké par Makolo.',
                        style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.76),
                          height: 1.35,
                        ),
                      ),
                    ],
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
