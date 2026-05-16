import rawCaseStudies from '../../data/case-studies.sample.json';
import type { CaseStudyRecord } from './types';

export const caseStudies = rawCaseStudies as unknown as CaseStudyRecord[];

export function findCaseStudyBySlug(slug: string) {
  return caseStudies.find((record) => record.slug === slug);
}