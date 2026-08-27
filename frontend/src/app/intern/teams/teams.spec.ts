import { ComponentFixture, TestBed } from '@angular/core/testing';

import { InternTeams } from './teams';

describe('InternTeams', () => {
  let component: InternTeams;
  let fixture: ComponentFixture<InternTeams>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [InternTeams],
    }).compileComponents();

    fixture = TestBed.createComponent(InternTeams);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
