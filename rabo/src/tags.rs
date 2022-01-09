use derive_more::{Display, Error, From};
use regex::Regex;
use std::boxed::Box;
use std::collections::HashSet;
use std::fmt;
use std::iter::FromIterator;

use crate::error::Result;

lazy_static! {
    static ref TAG_RE: Regex = Regex::new(r"^[A-Za-z0-9_]+$").unwrap();
    static ref LABEL_RE: Regex = Regex::new(r"^[A-Za-z0-9_]+$").unwrap();
}

#[derive(Default, Debug)]
struct SetOfStrings(HashSet<Box<str>>);

impl<'a, 'b> std::iter::FromIterator<&'b str> for SetOfStrings {
    fn from_iter<T: IntoIterator<Item = &'b str>>(iter: T) -> SetOfStrings {
        let mut set = SetOfStrings::default();
        for s in iter {
            set.0.insert(s.to_string().into_boxed_str());
        }
        set
    }
}

impl SetOfStrings {
    fn iter(&self) -> impl Iterator<Item = &str> {
        self.0.iter().map(|x| x.as_ref())
    }

    fn sorted(&self) -> Vec<&Box<str>> {
        let mut vec = self.0.iter().collect::<Vec<&Box<str>>>();
        vec.sort_by(|a, b| lexical_sort::natural_only_alnum_cmp(*a, *b));
        vec
    }
}

#[derive(Default, Debug)]
pub struct Tags(SetOfStrings);

#[derive(Debug, Display, Error, From)]
#[display(fmt = "invalid tag: {:?}", name)]
#[from(forward)]
pub struct InvalidTagError {
    name: Box<str>,
}

impl<'b> Tags {
    pub fn from_iter<T: IntoIterator<Item = &'b str>>(iter: T) -> Result<Tags> {
        let tags = Tags(SetOfStrings::from_iter(iter));
        for tag in tags.iter() {
            if !TAG_RE.is_match(tag) {
                Err(InvalidTagError::from(tag))?
            }
        }
        Ok(tags)
    }

    pub fn iter(&self) -> impl Iterator<Item = &str> {
        self.0.iter()
    }
}

impl fmt::Display for Tags {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        for tag in self.0.sorted() {
            write!(f, " ={}", tag)?;
        }
        Ok(())
    }
}

#[derive(Default, Debug)]
pub struct Labels(SetOfStrings);

#[derive(Debug, Display, Error, From)]
#[display(fmt = "invalid label: {:?}", name)]
#[from(forward)]
pub struct InvalidLabelError {
    name: Box<str>,
}

impl<'b> Labels {
    pub fn from_iter<T: IntoIterator<Item = &'b str>>(iter: T) -> Result<Labels> {
        let labels = Labels(SetOfStrings::from_iter(iter));
        for label in labels.iter() {
            if !TAG_RE.is_match(label) {
                Err(InvalidLabelError::from(label))?
            }
        }
        Ok(labels)
    }

    pub fn iter(&self) -> impl Iterator<Item = &str> {
        self.0.iter()
    }
}

impl fmt::Display for Labels {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        for tag in self.0.sorted() {
            write!(f, " [{}]", tag)?;
        }
        Ok(())
    }
}
