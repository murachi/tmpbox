export namespace validator {
  export function validateNameToken(val: string): boolean {
    return /^[a-z]\w*$/i.test(val);
  }
};
