use std::boxed::Box;
use std::collections::HashSet;
use std::fmt;

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
    fn sorted(&self) -> Vec<&Box<str>> {
        let mut vec = self.0.iter().collect::<Vec<&Box<str>>>();
        vec.sort_by(|a, b| human_sort::compare(*a, *b));
        vec
    }
}

#[derive(Default, Debug)]
pub struct Tags(SetOfStrings);

impl<'a, 'b> std::iter::FromIterator<&'b str> for Tags {
    fn from_iter<T: IntoIterator<Item = &'b str>>(iter: T) -> Tags {
        Tags(SetOfStrings::from_iter(iter))
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

impl<'a, 'b> std::iter::FromIterator<&'b str> for Labels {
    fn from_iter<T: IntoIterator<Item = &'b str>>(iter: T) -> Labels {
        Labels(SetOfStrings::from_iter(iter))
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
