import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AdminArticleDrafts } from './drafts';

describe('AdminArticleDrafts', () => {
  let component: AdminArticleDrafts;
  let fixture: ComponentFixture<AdminArticleDrafts>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AdminArticleDrafts],
    }).compileComponents();

    fixture = TestBed.createComponent(AdminArticleDrafts);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
