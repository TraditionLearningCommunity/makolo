import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../app/providers.dart';
import '../../auth/auth_repository.dart';
import '../../design/makolo_theme.dart';
import 'auth_components.dart';
import 'auth_entry_frame.dart';
import 'auth_error_messages.dart';

class SignupScreen extends StatefulWidget {
  const SignupScreen({
    super.key,
    required this.runtime,
    required this.onBackToLogin,
    required this.onAuthenticated,
  });

  final AppRuntime runtime;
  final ValueChanged<String> onBackToLogin;
  final VoidCallback onAuthenticated;

  @override
  State<SignupScreen> createState() => _SignupScreenState();
}

class _SignupScreenState extends State<SignupScreen> {
  final _formKey = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _username = TextEditingController();
  final _firstName = TextEditingController();
  final _lastName = TextEditingController();
  final _phone = TextEditingController();
  final _password = TextEditingController();
  final _passwordConfirm = TextEditingController();

  final _usernameFocus = FocusNode();
  final _firstNameFocus = FocusNode();
  final _lastNameFocus = FocusNode();
  final _phoneFocus = FocusNode();
  final _passwordFocus = FocusNode();
  final _passwordConfirmFocus = FocusNode();

  bool _busy = false;
  bool _showPassword = false;
  bool _showPasswordConfirm = false;
  bool _rememberOnDevice = false;
  String? _error;

  @override
  void dispose() {
    for (final controller in [
      _email,
      _username,
      _firstName,
      _lastName,
      _phone,
      _password,
      _passwordConfirm,
    ]) {
      controller.dispose();
    }
    for (final focus in [
      _usernameFocus,
      _firstNameFocus,
      _lastNameFocus,
      _phoneFocus,
      _passwordFocus,
      _passwordConfirmFocus,
    ]) {
      focus.dispose();
    }
    super.dispose();
  }

  String? _requiredEmail(String? value) {
    final email = value?.trim() ?? '';
    if (email.isEmpty || !email.contains('@')) {
      return 'Indiquez une adresse e-mail valide.';
    }
    return null;
  }

  String? _requiredUsername(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'Choisissez un nom d’utilisateur.';
    }
    return null;
  }

  String? _requiredPassword(String? value) {
    if (value == null || value.length < 8) {
      return 'Utilisez au moins 8 caractères.';
    }
    return null;
  }

  String? _confirmPassword(String? value) {
    if (value != _password.text) {
      return 'Les deux mots de passe doivent être identiques.';
    }
    return null;
  }

  Future<void> _submit() async {
    if (_busy || !_formKey.currentState!.validate()) return;
    final api = widget.runtime.api;
    if (api == null) {
      setState(() {
        _error = 'La création de compte est indisponible sur cette installation pour le moment.';
      });
      return;
    }

    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await AuthRepository(api, widget.runtime.tokens).registerAndLogin(
        email: _email.text.trim(),
        username: _username.text.trim(),
        password: _password.text,
        passwordConfirm: _passwordConfirm.text,
        firstName: _firstName.text.trim(),
        lastName: _lastName.text.trim(),
        phone: _phone.text.trim(),
        rememberOnDevice: _rememberOnDevice,
      );
      TextInput.finishAutofillContext();
      if (!mounted) return;
      widget.onAuthenticated();
    } on Object catch (error) {
      if (!mounted) return;
      setState(() => _error = signupErrorMessage(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  TextStyle _sectionStyle(BuildContext context) {
    return Theme.of(context).textTheme.titleLarge!
        .copyWith(color: Colors.white, fontWeight: FontWeight.w800);
  }

  @override
  Widget build(BuildContext context) {
    return AuthEntryFrame(
      title: 'Créer un compte',
      subtitle: 'Quelques informations suffisent pour commencer avec Makolo.',
      onBack: () => widget.onBackToLogin(_email.text.trim()),
      child: AutofillGroup(
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('Votre accès', style: _sectionStyle(context)),
              const SizedBox(height: MakoloSpacing.md),
              MakoloAuthField(
                fieldKey: const Key('signup-email'),
                label: 'Adresse e-mail',
                controller: _email,
                enabled: !_busy,
                keyboardType: TextInputType.emailAddress,
                autofillHints: const [AutofillHints.email],
                textInputAction: TextInputAction.next,
                prefixIcon: Icons.alternate_email,
                validator: _requiredEmail,
                onEditingComplete: () => _usernameFocus.requestFocus(),
              ),
              const SizedBox(height: MakoloSpacing.md),
              MakoloAuthField(
                fieldKey: const Key('signup-username'),
                label: 'Nom d’utilisateur',
                controller: _username,
                focusNode: _usernameFocus,
                enabled: !_busy,
                autofillHints: const [AutofillHints.username],
                textInputAction: TextInputAction.next,
                prefixIcon: Icons.person_outline,
                validator: _requiredUsername,
                onEditingComplete: () => _firstNameFocus.requestFocus(),
              ),
              const SizedBox(height: MakoloSpacing.xl),
              Text('Vous', style: _sectionStyle(context)),
              const SizedBox(height: MakoloSpacing.md),
              MakoloAuthField(
                label: 'Prénom (facultatif)',
                controller: _firstName,
                focusNode: _firstNameFocus,
                enabled: !_busy,
                autofillHints: const [AutofillHints.givenName],
                textInputAction: TextInputAction.next,
                prefixIcon: Icons.badge_outlined,
                onEditingComplete: () => _lastNameFocus.requestFocus(),
              ),
              const SizedBox(height: MakoloSpacing.md),
              MakoloAuthField(
                label: 'Nom (facultatif)',
                controller: _lastName,
                focusNode: _lastNameFocus,
                enabled: !_busy,
                autofillHints: const [AutofillHints.familyName],
                textInputAction: TextInputAction.next,
                prefixIcon: Icons.badge_outlined,
                onEditingComplete: () => _phoneFocus.requestFocus(),
              ),
              const SizedBox(height: MakoloSpacing.md),
              MakoloAuthField(
                label: 'Téléphone (facultatif)',
                controller: _phone,
                focusNode: _phoneFocus,
                enabled: !_busy,
                keyboardType: TextInputType.phone,
                autofillHints: const [AutofillHints.telephoneNumber],
                textInputAction: TextInputAction.next,
                prefixIcon: Icons.phone_outlined,
                onEditingComplete: () => _passwordFocus.requestFocus(),
              ),
              const SizedBox(height: MakoloSpacing.xl),
              Text('Sécurité', style: _sectionStyle(context)),
              const SizedBox(height: MakoloSpacing.xs),
              Text(
                'Au moins 8 caractères. Les règles de sécurité finales restent celles du serveur Makolo.',
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.76),
                  height: 1.35,
                ),
              ),
              const SizedBox(height: MakoloSpacing.md),
              MakoloAuthField(
                fieldKey: const Key('signup-password'),
                label: 'Mot de passe',
                controller: _password,
                focusNode: _passwordFocus,
                enabled: !_busy,
                obscureText: !_showPassword,
                autofillHints: const [AutofillHints.newPassword],
                textInputAction: TextInputAction.next,
                prefixIcon: Icons.lock_outline,
                validator: _requiredPassword,
                onEditingComplete: () => _passwordConfirmFocus.requestFocus(),
                suffixIcon: IconButton(
                  tooltip: _showPassword
                      ? 'Masquer le mot de passe'
                      : 'Afficher le mot de passe',
                  onPressed: _busy
                      ? null
                      : () => setState(() => _showPassword = !_showPassword),
                  icon: Icon(
                    _showPassword ? Icons.visibility_off : Icons.visibility,
                    color: MakoloColors.deep,
                  ),
                ),
              ),
              const SizedBox(height: MakoloSpacing.md),
              MakoloAuthField(
                fieldKey: const Key('signup-password-confirm'),
                label: 'Confirmer le mot de passe',
                controller: _passwordConfirm,
                focusNode: _passwordConfirmFocus,
                enabled: !_busy,
                obscureText: !_showPasswordConfirm,
                autofillHints: const [AutofillHints.newPassword],
                textInputAction: TextInputAction.done,
                prefixIcon: Icons.lock_outline,
                validator: _confirmPassword,
                onFieldSubmitted: (_) => _submit(),
                suffixIcon: IconButton(
                  tooltip: _showPasswordConfirm
                      ? 'Masquer la confirmation'
                      : 'Afficher la confirmation',
                  onPressed: _busy
                      ? null
                      : () => setState(
                          () => _showPasswordConfirm = !_showPasswordConfirm,
                        ),
                  icon: Icon(
                    _showPasswordConfirm
                        ? Icons.visibility_off
                        : Icons.visibility,
                    color: MakoloColors.deep,
                  ),
                ),
              ),
              const SizedBox(height: MakoloSpacing.md),
              MakoloQuickAccessChoice(
                value: _rememberOnDevice,
                onChanged: _busy
                    ? null
                    : (value) => setState(() => _rememberOnDevice = value),
              ),
              if (_error != null) ...[
                const SizedBox(height: MakoloSpacing.md),
                Semantics(
                  liveRegion: true,
                  child: Text(
                    _error!,
                    style: const TextStyle(
                      color: Color(0xFFFFDAD6),
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
              const SizedBox(height: MakoloSpacing.lg),
              MakoloAuthPrimaryButton(
                buttonKey: const Key('signup-submit'),
                label: 'Créer mon compte',
                busy: _busy,
                onPressed: _submit,
              ),
              const SizedBox(height: MakoloSpacing.sm),
              MakoloAuthTextAction(
                label: 'J’ai déjà un compte',
                onPressed: _busy
                    ? null
                    : () => widget.onBackToLogin(_email.text.trim()),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
