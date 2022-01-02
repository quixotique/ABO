use std::boxed::Box;
use std::collections::HashSet;
use std::fmt;

#[derive(Default, Debug)]
pub struct Tags {
    inner: HashSet<Box<str>>,
}

impl Tags {
    pub fn from_iter<'a, I: Iterator<Item = &'a str>>(iter: I) -> Tags {
        let mut tags = Tags::default();
        for s in iter {
            tags.inner.insert(s.to_string().into_boxed_str());
        }
        tags
    }
}

impl fmt::Display for Tags {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let mut vec = self.inner.iter().collect::<Vec<&Box<str>>>();
        vec.sort_by(|a, b| human_sort::compare(*a, *b));
        for tag in vec {
            write!(f, " ={}", tag)?;
        }
        Ok(())
    }
}
