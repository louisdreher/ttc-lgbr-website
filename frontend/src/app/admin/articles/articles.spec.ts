import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AdminArticles } from './articles';

describe('AdminArticles', () => {
  let component: AdminArticles;
  let fixture: ComponentFixture<AdminArticles>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AdminArticles],
    }).compileComponents();

    fixture = TestBed.createComponent(AdminArticles);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
