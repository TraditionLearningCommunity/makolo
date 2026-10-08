import 'dart:async';

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

enum _IdentifierAvailability {
  idle,
  checking,
  available,
  unavailable,
  unableToCheck,
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
  Timer? _draftTimer;
  Timer? _usernameAvailabilityTimer;
  int _usernameAvailabilityVersion = 0;
  _IdentifierAvailability _usernameAvailability = _IdentifierAvailability.idle;
  String? _usernameAvailabilityMessage;
  bool _restoringDraft = false;

  @override
  void initState() {
    super.initState();
    for (final controller in [
      _email,
      _username,
      _firstName,
      _lastName,
      _phone,
    ]) {
      controller.addListener(_scheduleDraftSave);
    }
    _username.addListener(_scheduleUsernameAvailabilityCheck);
    unawaited(_restoreDraft());
  }

  Future<void> _restoreDraft() async {
    final draft = await widget.runtime.interactions?.read('signup');
    if (!mounted || draft == null || draft.isEmpty) return;
    _restoringDraft = true;
    _email.text = draft['email'] is String ? draft['email'] as String : '';
    _username.text = draft['username'] is String
        ? draft['username'] as String
        : '';
    _firstName.text = draft['first_name'] is String
        ? draft['first_name'] as String
        : '';
    _lastName.text = draft['last_name'] is String
        ? draft['last_name'] as String
        : '';
    _phone.text = draft['phone'] is String ? draft['phone'] as String : '';
    _rememberOnDevice = draft['remember_on_device'] == true;
    _restoringDraft = false;
    if (mounted) setState(() {});
  }

  void _scheduleDraftSave() {
    if (_restoringDraft) return;
    _draftTimer?.cancel();
    _draftTimer = Timer(const Duration(milliseconds: 250), () {
      unawaited(
        widget.runtime.interactions?.save('signup', {
              'email': _email.text.trim(),
              'username': _username.text.trim(),
              'first_name': _firstName.text.trim(),
              'last_name': _lastName.text.trim(),
              'phone': _phone.text.trim(),
              'remember_on_device': _rememberOnDevice,
            }) ??
            Future<void>.value(),
      );
    });
  }

  @override
  void dispose() {
    _draftTimer?.cancel();
    _usernameAvailabilityTimer?.cancel();
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

  String? _optionalEmail(String? value) {
    final email = value?.trim() ?? '';
    if (email.isNotEmpty && !email.contains('@')) {
      return 'Indiquez une adresse e-mail valide ou laissez ce champ vide.';
    }
    return null;
  }

  String _loginHint() {
    final username = _normalizedUsername(_username.text);
    if (username.isNotEmpty) return '@$username';
    return _email.text.trim();
  }

  String _normalizedUsername(String value) {
    final trimmed = value.trim().toLowerCase();
    return trimmed.startsWith('@') ? trimmed.substring(1) : trimmed;
  }

  String? _localUsernameError(String value) {
    final normalized = _normalizedUsername(value);
    if (normalized.isEmpty) {
      return 'Choisissez un Identifiant Makolo.';
    }
    if (normalized.length < 3 || normalized.length > 30) {
      return 'Utilisez entre 3 et 30 caractères.';
    }
    final pattern = RegExp(r'^[a-z0-9](?:[a-z0-9._-]{1,28}[a-z0-9])?$');
    if (!pattern.hasMatch(normalized)) {
      return 'Utilisez lettres, chiffres, points, tirets ou underscores.';
    }
    const reserved = {
      'admin',
      'api',
      'help',
      'login',
      'logout',
      'makolo',
      'me',
      'support',
      'system',
    };
    if (reserved.contains(normalized)) {
      return 'Cet Identifiant Makolo est réservé.';
    }
    return null;
  }

  String? _requiredUsername(String? value) {
    final error = _localUsernameError(value ?? '');
    if (error != null) return error;
    if (_usernameAvailability == _IdentifierAvailability.unavailable) {
      return _usernameAvailabilityMessage ??
          'Cet Identifiant Makolo n’est pas disponible.';
    }
    return null;
  }

  void _scheduleUsernameAvailabilityCheck() {
    if (_restoringDraft) return;
    _usernameAvailabilityTimer?.cancel();
    _usernameAvailabilityVersion += 1;
    final version = _usernameAvailabilityVersion;
    final normalized = _normalizedUsername(_username.text);
    final localError = _localUsernameError(normalized);

    if (localError != null) {
      if (mounted) {
        setState(() {
          _usernameAvailability = _IdentifierAvailability.idle;
          _usernameAvailabilityMessage = null;
        });
      }
      return;
    }

    if (mounted) {
      setState(() {
        _usernameAvailability = _IdentifierAvailability.checking;
        _usernameAvailabilityMessage = 'Vérification…';
      });
    }

    _usernameAvailabilityTimer = Timer(
      const Duration(milliseconds: 400),
      () => unawaited(_checkUsernameAvailability(normalized, version)),
    );
  }

  Future<void> _checkUsernameAvailability(
    String normalized,
    int version,
  ) async {
    final api = widget.runtime.api;
    if (api == null) {
      if (!mounted || version != _usernameAvailabilityVersion) return;
      setState(() {
        _usernameAvailability = _IdentifierAvailability.unableToCheck;
        _usernameAvailabilityMessage = 'Impossible de vérifier pour le moment.';
      });
      return;
    }

    try {
      final response = await api.publicGet(
        'api/v1/accounts/auth/identifier/availability/?value=${Uri.encodeQueryComponent(normalized)}',
      );
      final payload = response.jsonObject();
      if (!mounted ||
          version != _usernameAvailabilityVersion ||
          _normalizedUsername(_username.text) != normalized) {
        return;
      }
      final available = payload['available'] == true;
      setState(() {
        _usernameAvailability = available
            ? _IdentifierAvailability.available
            : _IdentifierAvailability.unavailable;
        _usernameAvailabilityMessage = available
            ? 'Identifiant Makolo disponible.'
            : 'Cet Identifiant Makolo n’est pas disponible.';
      });
    } on Object {
      if (!mounted ||
          version != _usernameAvailabilityVersion ||
          _normalizedUsername(_username.text) != normalized) {
        return;
      }
      setState(() {
        _usernameAvailability = _IdentifierAvailability.unableToCheck;
        _usernameAvailabilityMessage = 'Impossible de vérifier pour le moment.';
      });
    }
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
      final email = _email.text.trim();
      await AuthRepository(api, widget.runtime.tokens).registerAndLogin(
        email: email.isEmpty ? null : email,
        username: _username.text.trim(),
        password: _password.text,
        passwordConfirm: _passwordConfirm.text,
        firstName: _firstName.text.trim(),
        lastName: _lastName.text.trim(),
        phone: _phone.text.trim(),
        rememberOnDevice: _rememberOnDevice,
      );
      TextInput.finishAutofillContext();
      await widget.runtime.interactions?.clear('signup');
      if (!mounted) return;
      widget.onAuthenticated();
    } on Object catch (error) {
      if (!mounted) return;
      setState(() => _error = signupErrorMessage(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AuthEntryFrame(
      title: 'Créer un compte',
      onBack: () => widget.onBackToLogin(_loginHint()),
      child: AutofillGroup(
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              MakoloAuthField(
                fieldKey: const Key('signup-email'),
                label: 'Adresse e-mail (facultatif)',
                controller: _email,
                enabled: !_busy,
                keyboardType: TextInputType.emailAddress,
                autofillHints: const [AutofillHints.email],
                textInputAction: TextInputAction.next,
                prefixIcon: Icons.alternate_email,
                validator: _optionalEmail,
                onEditingComplete: () => _usernameFocus.requestFocus(),
              ),
              const SizedBox(height: MakoloSpacing.md),
              MakoloAuthField(
                fieldKey: const Key('signup-username'),
                label: 'Identifiant Makolo',
                controller: _username,
                focusNode: _usernameFocus,
                enabled: !_busy,
                autofillHints: const [AutofillHints.username],
                textInputAction: TextInputAction.next,
                prefixIcon: Icons.person_outline,
                validator: _requiredUsername,
                onEditingComplete: () => _firstNameFocus.requestFocus(),
              ),
              if (_usernameAvailability != _IdentifierAvailability.idle) ...[
                const SizedBox(height: MakoloSpacing.xs),
                Semantics(
                  liveRegion: true,
                  child: Text(
                    _usernameAvailabilityMessage ?? '',
                    key: const Key('signup-username-availability'),
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: switch (_usernameAvailability) {
                        _IdentifierAvailability.available => Theme.of(
                          context,
                        ).colorScheme.primary,
                        _IdentifierAvailability.unavailable => Theme.of(
                          context,
                        ).colorScheme.error,
                        _IdentifierAvailability.unableToCheck => Theme.of(
                          context,
                        ).colorScheme.onSurfaceVariant,
                        _IdentifierAvailability.checking => Theme.of(
                          context,
                        ).colorScheme.onSurfaceVariant,
                        _IdentifierAvailability.idle => Theme.of(
                          context,
                        ).colorScheme.onSurfaceVariant,
                      },
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
              const SizedBox(height: MakoloSpacing.md),
              MakoloAuthField(
                fieldKey: const Key('signup-first-name'),
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
                fieldKey: const Key('signup-last-name'),
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
                fieldKey: const Key('signup-phone'),
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
                    : (value) {
                        setState(() => _rememberOnDevice = value);
                        _scheduleDraftSave();
                      },
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
              MakoloAuthSecondaryButton(
                label: 'J’ai déjà un compte',
                onPressed: _busy
                    ? null
                    : () => widget.onBackToLogin(_loginHint()),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
