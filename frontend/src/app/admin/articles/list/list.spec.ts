import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AdminArticleList } from './list';

describe('AdminArticleList', () => {
  let component: AdminArticleList;
  let fixture: ComponentFixture<AdminArticleList>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AdminArticleList],
    }).compileComponents();

    fixture = TestBed.createComponent(AdminArticleList);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
