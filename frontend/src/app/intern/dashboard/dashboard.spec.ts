import { ComponentFixture, TestBed } from '@angular/core/testing';

import { InternDashboard } from './dashboard';

describe('InternDashboard', () => {
  let component: InternDashboard;
  let fixture: ComponentFixture<InternDashboard>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [InternDashboard],
    }).compileComponents();

    fixture = TestBed.createComponent(InternDashboard);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
