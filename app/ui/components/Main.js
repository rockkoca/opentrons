import React, { Component } from 'react';
import { Switch, Route } from 'react-router';

import Home from './Home';
import Brand from './Brand';
import Calibrate from './Calibrate';
import Run from './Run';
import Load from './Load';
import Welcome from './Welcome';
import Status from './Status';

import styles from './Main.css';

export default class Main extends Component {
  render() {
    const { version, move, home, load, run, robotState } = this.props;
    return (
      <div className={styles.container}>
        <div className={styles.header}>
          <section className={styles.menu}>
            <Home {...{ home }} className={styles.home} />
            <Brand {...{ version }} className={styles.brand} />
          </section>
          <section className={styles.protocol} />
        </div>
        <div className={styles.task}>
          <Switch>
            <Route path="/" render={() => (<Welcome />)} />
            <Route path="/load" render={() => (<Load {...{ load }} />)} />
            <Route path="/calibrate" render={() => (<Calibrate {...{ robotState, move }} />)} />
            <Route path="/run" render={() => (<Run {...{ robotState, run }} />)} />
            <Route path="/welcome" render={() => (<Welcome />)} />
          </Switch>
        </div>
        <div className={styles.footer}>
          <Status />
        </div>
      </div>
    )
  }
}