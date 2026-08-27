import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AdminTeams } from './teams';

describe('AdminTeams', () => {
  let component: AdminTeams;
  let fixture: ComponentFixture<AdminTeams>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AdminTeams],
    }).compileComponents();

    fixture = TestBed.createComponent(AdminTeams);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
