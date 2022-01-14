use derive_more::{Constructor, Display, From};

pub type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

#[derive(Debug, From)]
#[from(forward)]
pub struct InputLoc {
    path: Option<Box<str>>,
    line_number: u32, // 0 == not known
}

impl std::fmt::Display for InputLoc {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        if !self.path.is_none() {
            let path = self.path.as_ref().unwrap();
            if self.line_number != 0 {
                write!(f, " at {}, line {}", path, self.line_number)
            } else {
                write!(f, " in {}", path)
            }
        } else if self.line_number != 0 {
            write!(f, " at line {}", self.line_number)
        } else {
            Ok(())
        }
    }
}

impl InputLoc {
    pub fn new(line_number: u32) -> InputLoc {
        InputLoc {
            path: None,
            line_number,
        }
    }

    fn with_path(&self, path: &str) -> InputLoc {
        InputLoc {
            path: Some(path.to_string().into_boxed_str()),
            line_number: self.line_number,
        }
    }
}

#[derive(Constructor, Debug, From, Display)]
#[from(forward)]
#[display(fmt = "{}{}", source, loc)]
pub struct InputError {
    loc: InputLoc,
    source: Box<dyn std::error::Error>,
}

impl std::error::Error for InputError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        Some(&*self.source)
    }
}
impl InputError {
    pub fn set_path(&mut self, path: &str) -> &InputError {
        self.loc = self.loc.with_path(path);
        self
    }
}

#[cfg(test)]
use derive_more::Error;

#[cfg(test)]
#[derive(Debug, Display, Error, From)]
#[display(fmt = "test failed: {:?}", message)]
#[from(forward)]
pub struct Fail {
    message: Box<str>,
}
