import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  inject,
  signal,
} from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { catchError, finalize, forkJoin, map, of, Subject, switchMap } from 'rxjs';
import { UserApi, userError } from '../user-api.service';
import { Member, MemberData, MemberOption, USER_ROLES, UserWrite } from '../user.models';
import { AuthService } from '../../../core/auth/auth.service';

@Component({
  selector: 'app-user-form',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './user-form.html',
  styleUrls: ['../../articles/cms.css', './user-form.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class UserForm {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly api = inject(UserApi);
  private readonly router = inject(Router);
  private readonly auth = inject(AuthService);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly destroyRef = inject(DestroyRef);
  private readonly routeId = inject(ActivatedRoute).snapshot.paramMap.get('id');
  readonly id = this.routeId === null ? null : Number(this.routeId);
  readonly roles = USER_ROLES;
  readonly options = signal<MemberOption[]>([]);
  readonly loading = signal(true);
  readonly loadFailed = signal(false);
  readonly saving = signal(false);
  readonly memberLoading = signal(false);
  readonly memberReady = signal(true);
  readonly error = signal('');
  readonly mode = signal('new');
  readonly submitted = signal(false);
  readonly today = new Date().toISOString().slice(0, 10);
  private readonly selectedMember = new Subject<number | null>();
  readonly textFields = [
    { key: 'first_name', label: 'Vorname', required: true, type: 'text' },
    { key: 'last_name', label: 'Nachname', required: true, type: 'text' },
    { key: 'email', label: 'Kontakt-E-Mail', required: false, type: 'email' },
    { key: 'phone', label: 'Telefon', required: false, type: 'tel' },
    { key: 'mobile', label: 'Mobiltelefon', required: false, type: 'tel' },
    { key: 'street', label: 'Straße', required: false, type: 'text' },
    { key: 'house_number', label: 'Hausnummer', required: false, type: 'text' },
    { key: 'postal_code', label: 'Postleitzahl', required: false, type: 'text' },
    { key: 'city', label: 'Ort', required: false, type: 'text' },
  ] as const;
  readonly dateFields = [
    { key: 'birth_date', label: 'Geburtsdatum' },
    { key: 'joined_at', label: 'Eintrittsdatum' },
    { key: 'membership_end_date', label: 'Austrittsdatum' },
    { key: 'eligible_since', label: 'Spielberechtigt seit' },
    { key: 'ttc_eligible_since', label: 'Für den TTC spielberechtigt seit' },
  ] as const;
  readonly memberForm = this.fb.group({
    first_name: ['', [Validators.required, Validators.pattern(/\S/), Validators.maxLength(200)]],
    last_name: ['', [Validators.required, Validators.pattern(/\S/), Validators.maxLength(200)]],
    birth_date: '',
    joined_at: '',
    eligible_since: '',
    ttc_eligible_since: '',
    membership_end_date: '',
    is_active: true,
    phone: '',
    mobile: '',
    email: ['', Validators.email],
    street: '',
    house_number: '',
    postal_code: '',
    city: '',
  });
  readonly form = this.fb.group({
    name: ['', [Validators.required, Validators.pattern(/\S/), Validators.maxLength(200)]],
    email: ['', [Validators.required, Validators.email]],
    is_active: true,
    roles: this.fb.group({ ADMIN: false, EDITOR: false, TEAM_REPORTER: false }),
    memberMode: 'new',
    memberId: '',
    member: this.memberForm,
    sendInvitation: true,
  });

  constructor() {
    if (this.id !== null && (!Number.isSafeInteger(this.id) || this.id <= 0)) {
      this.loading.set(false);
      this.loadFailed.set(true);
      this.error.set('Ungültige Benutzer-ID. Bitte öffne das Konto über die Benutzerübersicht.');
      return;
    }
    this.selectedMember
      .pipe(
        switchMap((id) => {
          if (id === null) return of(null);
          this.memberLoading.set(true);
          this.memberReady.set(false);
          this.error.set('');
          return this.api.member(id).pipe(
            catchError((error) => {
              this.error.set(userError(error));
              return of(null);
            }),
          );
        }),
        takeUntilDestroyed(),
      )
      .subscribe((member) => {
        this.memberLoading.set(false);
        if (member) {
          this.fillMember(member);
          this.memberReady.set(true);
        }
      });
    this.form.controls.memberMode.valueChanges.pipe(takeUntilDestroyed()).subscribe((mode) => {
      this.mode.set(mode);
      this.selectedMember.next(null);
      this.form.controls.memberId.setValue('');
      this.memberForm.reset();
      if (mode === 'none') this.memberForm.disable();
      else this.memberForm.enable();
      this.memberReady.set(mode !== 'existing');
    });
    this.form.controls.memberId.valueChanges.pipe(takeUntilDestroyed()).subscribe((id) => {
      if (this.mode() === 'existing') {
        this.memberReady.set(false);
        this.selectedMember.next(Number(id) || null);
      }
    });
    forkJoin({ options: this.api.members(), user: this.id ? this.api.get(this.id) : of(null) })
      .pipe(takeUntilDestroyed())
      .subscribe({
        next: ({ options, user }) => {
          this.options.set(options);
          if (user) {
            const mode = user.member_id ? 'existing' : 'none';
            this.mode.set(mode);
            this.form.patchValue(
              {
                name: user.name,
                email: user.email,
                is_active: user.is_active,
                roles: {
                  ADMIN: user.roles.includes('ADMIN'),
                  EDITOR: user.roles.includes('EDITOR'),
                  TEAM_REPORTER: user.roles.includes('TEAM_REPORTER'),
                },
                memberMode: mode,
                memberId: user.member_id ? String(user.member_id) : '',
                sendInvitation: false,
              },
              { emitEvent: false },
            );
            if (user.member) this.fillMember(user.member);
            else this.memberForm.disable();
          }
          this.loading.set(false);
        },
        error: (error) => {
          this.error.set(userError(error));
          this.loading.set(false);
          this.loadFailed.set(true);
        },
      });
  }

  private fillMember(member: Member): void {
    this.memberForm.patchValue({
      first_name: member.first_name,
      last_name: member.last_name,
      is_active: member.is_active,
      birth_date: member.birth_date ?? '',
      joined_at: member.joined_at ?? '',
      eligible_since: member.eligible_since ?? '',
      ttc_eligible_since: member.ttc_eligible_since ?? '',
      membership_end_date: member.membership_end_date ?? '',
      phone: member.phone ?? '',
      mobile: member.mobile ?? '',
      email: member.email ?? '',
      street: member.street ?? '',
      house_number: member.house_number ?? '',
      postal_code: member.postal_code ?? '',
      city: member.city ?? '',
    });
  }

  canLeave(): boolean {
    return (
      !this.saving() && (!this.form.dirty || window.confirm('Ungespeicherte Änderungen verwerfen?'))
    );
  }

  submit(): void {
    if (this.saving() || this.memberLoading() || this.loading() || this.loadFailed()) return;
    this.submitted.set(true);
    this.error.set('');
    if (this.form.invalid || !this.memberReady()) {
      this.form.markAllAsTouched();
      this.error.set(
        'Bitte fülle alle Pflichtfelder korrekt aus und wähle gegebenenfalls ein Mitglied.',
      );
      this.host.nativeElement
        .querySelector<HTMLElement>('input.ng-invalid, select.ng-invalid')
        ?.focus();
      return;
    }
    const raw = this.form.getRawValue();
    const m = raw.member;
    if (
      raw.memberMode !== 'none' &&
      ((m.birth_date && m.birth_date > this.today) ||
        (m.joined_at && m.membership_end_date && m.membership_end_date < m.joined_at))
    ) {
      this.error.set('Bitte prüfe Geburtsdatum und die Reihenfolge von Eintritt und Austritt.');
      return;
    }
    const optional = (value: string) => value.trim() || null;
    const member: MemberData | null =
      raw.memberMode === 'none'
        ? null
        : {
            first_name: m.first_name.trim(),
            last_name: m.last_name.trim(),
            is_active: m.is_active,
            birth_date: optional(m.birth_date),
            joined_at: optional(m.joined_at),
            eligible_since: optional(m.eligible_since),
            ttc_eligible_since: optional(m.ttc_eligible_since),
            membership_end_date: optional(m.membership_end_date),
            email: optional(m.email),
            phone: optional(m.phone),
            mobile: optional(m.mobile),
            street: optional(m.street),
            house_number: optional(m.house_number),
            postal_code: optional(m.postal_code),
            city: optional(m.city),
          };
    const data: UserWrite = {
      name: raw.name.trim(),
      email: raw.email.trim().toLowerCase(),
      is_active: raw.is_active,
      roles: this.roles.filter((role) => raw.roles[role.value]).map((role) => role.value),
      member_id: raw.memberMode === 'existing' ? Number(raw.memberId) : null,
      member,
    };
    this.saving.set(true);
    const request = this.id
      ? this.api.update(this.id, data).pipe(map(() => ({ id: this.id! })))
      : this.api.create(data);
    request
      .pipe(
        switchMap((result) => {
          this.form.markAsPristine();
          const message = this.id ? 'Benutzer gespeichert.' : 'Benutzer angelegt.';
          if (!this.id && raw.sendInvitation && raw.is_active) {
            return this.api.passwordLink(result.id).pipe(
              map(() => message + ' Einladungslink versendet.'),
              catchError((error) =>
                of(message + ' Einladung nicht versendet: ' + userError(error)),
              ),
            );
          }
          return of(message);
        }),
        finalize(() => this.saving.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (message) => {
          this.api.notice.set(message);
          this.saving.set(false);
          if (this.id === this.auth.user()?.id) {
            this.auth
              .loadCurrentUser()
              .pipe(takeUntilDestroyed(this.destroyRef))
              .subscribe({
                next: (me) =>
                  void this.router.navigate([
                    me.roles.includes('ADMIN') ? '/admin/users' : '/intern',
                  ]),
                error: () => {
                  this.auth.clearSession();
                  void this.router.navigate(['/login']);
                },
              });
          } else void this.router.navigate(['/admin/users']);
        },
        error: (error) => this.error.set(userError(error)),
      });
  }
}
